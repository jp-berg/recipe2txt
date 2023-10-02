# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.
"""
Module that provides a common interface for CLI-arguments and config files.

Since most parameters provided by the command line rarely change between program uses it makes sense to provide a
config-file to the user, so that tedious retyping of favored options can be avoided. And since most parameters a
program needs to derive either a CLI-option or a config option are the same, there should be a central place to
configure both.
The config-file-format used is TOML (https://toml.io)
"""
import argparse
import os
import sys
import textwrap
from enum import unique
from pathlib import Path
from typing import Any, TypeVar, Generic, Iterable, Final, LiteralString

from recipe2txt.utils.conditional_imports import StrEnum
from recipe2txt.utils.conditional_imports import tomllib
from recipe2txt.utils.misc import ensure_accessible_file_critical, File


def short_flag(long_name: str) -> str:
    """
    Creates a shortened version of a long flag-name

    Uses the first letter of each word. Words should be separated by '-'.

    Examples:
        'version' -> '-v'
        'long-name' -> '-ln'

    Args:
        long_name (): the name for the long version of the flag name

    Returns:
        A shortened version of the long flag.

    """
    segments = long_name.split("-")
    starting_letters = [segment.strip()[0] for segment in segments if segment]
    return "-" + "".join(starting_letters)


def obj2toml(o: Any) -> str:
    """
    Converts an object to a TOML-string

    Supports (unnested) lists and dictionaries as well as strings and booleans.
    Args:
        o (): The object to stringify

    Returns:
        A string that can be used as a value to a TOML-key
    """
    if isinstance(o, list):
        s = "["
        for e in o:
            s += f"{obj2toml_i(e)}, "
        return s[:-2] + "]"
    if isinstance(o, dict):
        s = "{"
        for key, value in o.items():
            s += f"{obj2toml_i(key)}: {obj2toml_i(value)}, "
        return s[:-2] + "}"
    return obj2toml_i(o)


def obj2toml_i(o: Any) -> str:
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, str):
        return f"'{o}'"
    return str(o)


@unique
class ArgKey(StrEnum):
    """Enum describing the ke"""
    help = "help"
    default = "default"
    choices = "choices"
    type = "type"
    action = "action"
    nargs = "nargs"


class BasicOption:
    """
    Generates an option in its most basic form

     Useful for e.g. "--foo bar" for the CLI and  "foo = 'bar'" for the TOML-file
    """

    help_wrapper = textwrap.TextWrapper(width=72,
                                        initial_indent="# ",
                                        subsequent_indent="# ",
                                        break_long_words=False,
                                        break_on_hyphens=False)
    """textwrap-instance for the help-strings in the TOML-file"""

    def __init__(self, name: str, help_str: str, default: Any = None, short: str | None = ""):
        name = name.strip()
        if name.startswith('-'):
            raise ValueError("'name' should just be the name of the flag without any leading '-'")
        self.name = name
        self.names = ["--" + name]

        if short is not None:
            short = short.strip()
            if short.startswith('-'):
                raise ValueError("'short' should just be the name of the flag without any leading '-'")
            if len(short) >= len(name):
                raise ValueError("'short' is not shorter than 'name'")
            if short:
                self.names.append('-' + short)
            else:
                self.names.append(short_flag(name))
        self.arguments = {ArgKey.help: help_str, ArgKey.default: default}

    def add_to_parser(self, parser: argparse.ArgumentParser) -> None:
        help_tmp = self.arguments[ArgKey.help]
        if self.arguments[ArgKey.default] is not None:
            self.arguments[ArgKey.help] = f"{self.arguments[ArgKey.help]} (default: '{self.arguments[ArgKey.default]}')"
        parser.add_argument(*self.names, **self.arguments)
        self.arguments[ArgKey.help] = help_tmp

    def to_toml_str(self) -> str:
        """Generates a string representation of this option that also represents a valid TOML-assignment."""
        return self.to_toml_str_intern("")

    def to_toml_str_intern(self, value_comment: str) -> str:
        default_str = obj2toml(self.arguments[ArgKey.default])
        help_str = BasicOption.help_wrapper.fill(self.arguments[ArgKey.help])
        return f"\n\n\n{help_str}\n\n#{self.name} = {default_str}{value_comment}\n"

    def to_toml(self, file: File | None = None) -> None:
        """Appends this Option and its default-value to a TOML-file"""
        if file:
            with file.open("a") as f:
                f.write(self.to_toml_str())

    def toml_valid(self, value: Any) -> bool:
        """Decides whether the TOML-representation for this option returns a valid value"""
        return bool(value)

    def from_toml(self, toml: dict[str, Any]) -> bool:
        """
        Retrieves a value for this option from a TOML-dict.

        The value is checked for validity. If its valid it replaces the current default-value
        Args:
            toml = A dictionary containing TOML-key-value-pairs (e.g. generated by `:py:meth:tomllib.load`)

        Returns:
            True if  a valid value could be extracted from the TOML-file, False otherwise
        """
        value = toml.get(self.name)
        if self.toml_valid(value):
            self.arguments[ArgKey.default] = value
            return True
        return False


T = TypeVar('T')
"""Generic Type"""


class ChoiceOption(BasicOption, Generic[T]):
    """
    Option-Subclass representing the corresponding :py:meth:`argparse.ArgumentParser.add_argument`-option, with the
    parameter 'choices' set.

    It provides the ability to select from a restricted set of choices.
    """

    def __init__(self, name: str, help_str: str, default: T, choices: Iterable[T], short: str | None = ""):
        if default not in choices:
            raise ValueError(f"Parameter {default=} not in {choices=}")
        super().__init__(name, help_str, default, short)
        self.arguments[ArgKey.choices] = choices

    def to_toml_str(self) -> str:
        choice_str = " | ".join([obj2toml(choice) for choice in self.arguments[ArgKey.choices]])
        return super().to_toml_str_intern(f" # Possible values: {choice_str}\n")

    def toml_valid(self, value: Any) -> bool:
        if value not in self.arguments[ArgKey.choices]:
            return False
        return True


class TypeOption(BasicOption):
    """
    Option-Subclass representing the corresponding :py:meth:`argparse.ArgumentParser.add_argument`-option, with the
    parameter 'type' set.

    Converts input-strings to the given type instead just parsing everything as a string.
    Since the value is being parsed from TOML it should be representable as such (i.e. probably only 'int' and 'float'
    make sense as types).
    """
    def __init__(self, name: str, help_str: str, default: Any, t: type, short: str | None = ""):
        if not isinstance(default, t):
            raise ValueError("Parameter {default=} does not match type {t=}")
        super().__init__(name, help_str, default, short)
        self.arguments[ArgKey.type] = t

    def toml_valid(self, value: Any) -> bool:
        if not (t := self.arguments.get(ArgKey.type)):
            raise RuntimeError("'argument_args' does not contain 'type' (but it should)")
        return isinstance(value, t)


class BoolOption(BasicOption):
    """
    Option-Subclass representing the corresponding :py:meth:`argparse.ArgumentParser.add_argument`-option, with the
    parameter 'action' set to 'store_true'.
    """

    def __init__(self, name: str, help_str: str, default: bool = False, short: str | None = ""):
        super().__init__(name, help_str, default, short)
        self.arguments[ArgKey.action] = "store_true"

    def to_toml_str(self) -> str:
        return super().to_toml_str_intern(" # Possible values: true | false")

    def toml_valid(self, value: Any) -> bool:
        if value not in (True, False):
            return False
        return True


class NArgOption(BasicOption):
    """
    Option-Subclass representing the corresponding :py:meth:`argparse.ArgumentParser.add_argument`-option, with the
    parameter 'nargs' set to '+'.

    It differs from the method by providing an empty list instead of failing if the option is not explicitly set.
    """
    def __init__(self, name: str, help_str: str, default: list[Any] | None = None, short: str | None = ""):
        d = [] if default is None else default
        super().__init__(name, help_str, d, short)
        self.arguments[ArgKey.nargs] = '+'

    def toml_valid(self, value: Any) -> bool:
        return isinstance(value, list)


CFG_PREAMBLE: Final[LiteralString] = """#%s
# Configuration file for the program %s
#
# Every option listed here has a CLI-pendant that it mirrors in function.
# If an option is defined here it will override the default-value for that
# option.
# Options defined here will be overridden by CLI arguments.
#
# This means that if the program expects a value for the option 'foo' it will
# first try to parse 'foo' from the CLI args, failing that it will try to find
# a value for 'foo' in this file, failing that it will use the default value
# defined in its source code.
#
# To recover the original file simply delete this file and run the program.
# (e.g. 'recipe2txt --help')
#
# For information about this file-format, please visit: https://toml.io
#%s


"""
"""
Help text explaining how the config-file works.

Should be written to the beginning of every config file.

Takes three %-formatting-args: first and third are pretty-print-borders, the second is the name of the program the
config-file belongs to.
"""


class ArgConfig:
    """
    Unified API for CLI-arguments and TOML-config-files.

    Checks if there is a config-file already available. If there is such a file, every option that is added tries to
    retrieve a default-value from it, otherwise the option will fall back onto the given default. If no config-file is
    available, a new one will be created and every option will write a TOML-key-value-pair-representation of itself
    to the file while being added.
    """

    def __init__(self,
                 parser: argparse.ArgumentParser,
                 config_dir: Path):
        self.parser = parser
        path = config_dir / f"{parser.prog}.toml"
        self.existed_before = path.is_file()
        self.file = ensure_accessible_file_critical(path)
        if self.existed_before:
            with self.file.open("rb") as cfg:
                try:
                    self.toml = tomllib.load(cfg)
                except tomllib.TOMLDecodeError as e:
                    msg = f"The config-file ({path}) seems to be misconfigured ({e})." \
                          " Fix the error or delete the file and generate a new one by running" \
                          " the program with any argument (eg. 'recipe2txt --help')"
                    print(msg, file=sys.stderr)
                    sys.exit(os.EX_DATAERR)
        else:
            self.file.write_text(CFG_PREAMBLE % (80 * '*', parser.prog, 80 * '*'))

    def error_exit(self):
        if not self.existed_before:
            try:
                os.remove(self.file)
            except FileNotFoundError:
               pass

    def _add_option(self, option: type, args: tuple[Any, ...]) -> None:
        try:
            o = option(*args)
            if self.existed_before:
                o.from_toml(self.toml)
            else:
                o.to_toml(self.file)
            o.add_to_parser(self.parser)
        except argparse.ArgumentError as e:
            self.error_exit()
            raise ValueError(e) from None
        except Exception as e:
            self.error_exit()
            raise e

    def add_arg(self, name: str, help_str: str, default: Any = None, short: str | None = "") -> None:
        """
        Register a standard argument consisting of a string name, expecting a string value.

        Args:
            name (): The name of the option. Will set an argparse-flag '--name' and will be the key in the
                TOML-key-value-pair. Cannot start with an '-'.
            help_str (): Description of the option. Will be the help-text for the argparse-flag and a comment just above
                the TOML-key-value-pair corresponding to this option.
            default (): The value that should be used if no other value is provided via CLI or TOML. Will be used as the
                initial value in the TOML-key-value-pair.
            short (): Whether there should exist a short version of the argparse-flag and what it should be.
                If set to 'None' no short version will be generated.
                If set to an empty string a short version will be derived from 'name'.
                If set to a string, the string will be used. Cannot start with an '-' and cannot contain more characters
                    than 'name'
        """
        self._add_option(BasicOption, (name, help_str, default, short))

    def add_choice(self, name: str, help_str: str, default: T, choices: Iterable[T], short: str | None = "") -> None:
        """
        Register a choice, prompting the user to select from a restricted set of values.

        Args:
            name (): see :py:meth:`ArgConfig.add_arg`
            help_str (): see :py:meth:`ArgConfig.add_arg`
            default (): Must be a value from 'choices'. See :py:meth:`ArgConfig.add_arg`
            choices (): A set of values the user can choose from
            short (): see :py:meth:`ArgConfig.add_arg`
        """
        self._add_option(ChoiceOption, (name, help_str, default, choices, short))

    def add_type(self, name: str, help_str: str, default: Any, t: type, short: str | None = "") -> None:
        """
        Register an argument with a certain type.

        Since the type has to be expressable in the TOML-format only 'int' and 'float' should make sense.
        Args:
            name (): see :py:meth:`ArgConfig.add_arg`
            help_str (): see :py:meth:`ArgConfig.add_arg`
            default (): Must be of type 't'. See :py:meth:`ArgConfig.add_arg`
            t (): The type of the option. Should be representable as TOML-string
            short (): see :py:meth:`ArgConfig.add_arg`
        """
        self._add_option(TypeOption, (name, help_str, default, t, short))

    def add_bool(self, name: str, help_str: str, default: bool = False, short: str | None = "") -> None:
        """
        Register a boolean argument

        Args:
            name (): see :py:meth:`ArgConfig.add_arg`
            help_str (): see :py:meth:`ArgConfig.add_arg`
            default (): See :py:meth:`ArgConfig.add_arg`
            short (): see :py:meth:`ArgConfig.add_arg`
        """
        self._add_option(BoolOption, (name, help_str, default, short))

    def add_narg(self, name: str, help_str: str, default: list[Any] | None = None, short: str | None = "") -> None:
        """
       Register an argument taking one or more elements.

       Args:
           name (): see :py:meth:`ArgConfig.add_arg`
           help_str (): see :py:meth:`ArgConfig.add_arg`
           default (): See :py:meth:`ArgConfig.add_arg`
           short (): see :py:meth:`ArgConfig.add_arg`
        """
        self._add_option(NArgOption, (name, help_str, default, short))
        