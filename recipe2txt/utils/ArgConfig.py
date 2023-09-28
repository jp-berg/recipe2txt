import argparse
import os
import sys
import textwrap
from enum import unique
from pathlib import Path
from typing import Any, TypeVar, Generic, Iterable, Final, LiteralString

from xdg_base_dirs import xdg_config_home

from recipe2txt.utils.conditional_imports import StrEnum
from recipe2txt.utils.conditional_imports import tomllib
from recipe2txt.utils.misc import ensure_accessible_file_critical, File


def short_flag(long_name: str) -> str:
    long_name = long_name.strip()
    segments = long_name.split("-")
    starting_letters = [segment.strip()[0] for segment in segments if segment]
    return "-" + "".join(starting_letters)


def obj2toml(o: Any) -> str:
    if isinstance(o, list):
        return str([obj2toml_i(e) for e in o])
    if isinstance(o, dict):
        return str({obj2toml_i(key): obj2toml_i(value) for key, value in o.items()})
    return obj2toml_i(o)


def obj2toml_i(o: Any) -> str:
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, str):
        return f"'{o}'"
    return str(o)


@unique
class ArgKey(StrEnum):
    help = "help"
    default = "default"
    choices = "choices"
    type = "type"
    action = "action"
    nargs = "nargs"


class BasicOption:
    help_wrapper = textwrap.TextWrapper(width=72,
                                        initial_indent="# ",
                                        subsequent_indent="# ",
                                        break_long_words=False,
                                        break_on_hyphens=False)

    def __init__(self, name: str, help_str: str, default: Any = None, has_short: bool = True):
        name = name.strip()
        if name.startswith('-'):
            raise ValueError("'name' should just be the name of the flag without any leading '-'")
        self.name = name
        self.names = ["--" + name]
        if has_short:
            self.names.append(short_flag(name))
        self.arguments = {ArgKey.help: help_str, ArgKey.default: default}

    def add_to_parser(self, parser: argparse.ArgumentParser) -> None:
        help_tmp = self.arguments[ArgKey.help]
        if self.arguments[ArgKey.default] is not None:
            self.arguments[ArgKey.help] = f"{self.arguments[ArgKey.help]} (default: '{self.arguments[ArgKey.default]}')"
        parser.add_argument(*self.names, **self.arguments)  # type: ignore [misc]
        self.arguments[ArgKey.help] = help_tmp

    def to_toml_str(self) -> str:
        return self.to_toml_str_intern("")

    def to_toml_str_intern(self, value_comment: str) -> str:
        default_str = obj2toml(self.arguments[ArgKey.default])
        help_str = BasicOption.help_wrapper.fill(self.arguments[ArgKey.help])
        return f"\n\n\n{help_str}\n\n#{self.name} = {default_str}{value_comment}\n"

    def to_toml(self, file: File | None = None) -> None:
        if file:
            with file.open("a") as f:
                f.write(self.to_toml_str())

    def toml_valid(self, value: Any) -> bool:
        return bool(value)

    def from_toml(self, toml: dict[str, Any]) -> bool:
        value = toml.get(self.name)
        if self.toml_valid(value):
            self.arguments[ArgKey.default] = value
            return True
        return False


T = TypeVar('T')


class ChoiceOption(BasicOption, Generic[T]):

    def __init__(self, name: str, help_str: str, default: T, choices: Iterable[T], has_short: bool = True):
        if default not in choices:
            raise ValueError(f"Parameter {default=} not in {choices=}")
        super().__init__(name, help_str, default, has_short)
        self.arguments[ArgKey.choices] = choices

    def to_toml_str(self) -> str:
        choice_str = " | ".join([obj2toml(choice) for choice in self.arguments[ArgKey.choices]])
        return super().to_toml_str_intern(f" # Possible values: {choice_str}\n")

    def toml_valid(self, value: Any) -> bool:
        if value not in self.arguments[ArgKey.choices]:
            return False
        return True


class TypeOption(BasicOption):

    def __init__(self, name: str, help_str: str, default: Any, t: type, has_short: bool = True):
        if not isinstance(default, t):
            raise ValueError("Parameter {default=} does not match type {t=}")
        super().__init__(name, help_str, default, has_short)
        self.arguments[ArgKey.type] = t

    def toml_valid(self, value: Any) -> bool:
        if not (t := self.arguments.get(ArgKey.type)):
            raise RuntimeError("'argument_args' does not contain 'type' (but it should)")
        return isinstance(value, t)


class BoolOption(BasicOption):

    def __init__(self, name: str, help_str: str, default: bool = False, has_short: bool = True):
        super().__init__(name, help_str, default, has_short)
        self.arguments[ArgKey.action] = "store_true"

    def to_toml_str(self) -> str:
        return super().to_toml_str_intern(" # Possible values: true | false")

    def toml_valid(self, value: Any) -> bool:
        if value not in (True, False):
            return False
        return True


class NArgOption(BasicOption):

    def __init__(self, name: str, help_str: str, default: list[Any] | None = None, has_short: bool = True):
        d = [] if default is None else default
        super().__init__(name, help_str, d, has_short)
        self.arguments[ArgKey.nargs] = '+'

    def toml_valid(self, value: Any) -> bool:
        return isinstance(value, list)


CFG_PREAMBLE: Final[LiteralString] = """
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


"""


class ArgConfig:

    def __init__(self,
                 parser: argparse.ArgumentParser,
                 config_dir: str | Path | None = None):
        self.parser = parser
        config_dir = config_dir if config_dir else xdg_config_home()
        config_path = Path(config_dir) / f"{parser.prog}.toml"
        self.existed_before = config_path.is_file()
        self.config_file = ensure_accessible_file_critical(config_path)
        if self.existed_before:
            with self.config_file.open("rb") as cfg:
                try:
                    self.toml = tomllib.load(cfg)
                except tomllib.TOMLDecodeError as e:
                    msg = f"The config-file ({config_path}) seems to be misconfigured ({e})." \
                          " Fix the error or delete the file and generate a new one by running" \
                          " the program with any argument (eg. 'recipe2txt --help')"
                    print(msg, file=sys.stderr)
                    sys.exit(os.EX_DATAERR)
        else:
            self.config_file.write_text(CFG_PREAMBLE % parser.prog)

    def add_option(self, option: BasicOption) -> None:
        if self.existed_before:
            option.from_toml(self.toml)
        else:
            option.to_toml(self.config_file)
        option.add_to_parser(self.parser)

    def add_arg(self, name: str, help_str: str, default: Any = None, has_short: bool = True) -> None:
        self.add_option(BasicOption(name, help_str, default, has_short))

    def add_choice(self, name: str, help_str: str, default: T, choices: Iterable[T], has_short: bool = True) -> None:
        self.add_option(ChoiceOption(name, help_str, default, choices, has_short))

    def add_type(self, name: str, help_str: str, default: Any, t: type, has_short: bool = True) -> None:
        self.add_option(TypeOption(name, help_str, default, t, has_short))

    def add_bool(self, name: str, help_str: str, default: bool = False, has_short: bool = True) -> None:
        self.add_option(BoolOption(name, help_str, default, has_short))

    def add_narg(self, name: str, help_str: str, default: list[Any] | None = None, has_short: bool = True) -> None:
        self.add_option(NArgOption(name, help_str, default, has_short))
