import argparse
import textwrap
from enum import unique
from typing import Any, TypeVar, Generic, Iterable

from recipe2txt.utils.conditional_imports import StrEnum


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
            self.arguments[ArgKey.help] = f"{self.arguments[ArgKey.help]} (default: {self.arguments[ArgKey.default]})"
        parser.add_argument(*self.names, **self.arguments)  # type: ignore [misc]
        self.arguments[ArgKey.help] = help_tmp

    def to_toml(self) -> str:
        default_str = obj2toml(self.arguments[ArgKey.default])
        return BasicOption.help_wrapper.fill(self.arguments[ArgKey.help]) + f"\n#{self.name} = {default_str}\n"

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

    def __init__(self, name: str, help_str: str, default: T, choices: Iterable[T]):
        if default not in choices:
            raise ValueError(f"Parameter {default=} not in {choices=}")
        super().__init__(name, help_str, default)
        self.arguments[ArgKey.choices] = choices

    def toml_valid(self, value: Any) -> bool:
        if value not in self.arguments[ArgKey.choices]:
            return False
        return True


class TypeOption(BasicOption):

    def __init__(self, name: str, help_str: str, default: Any, t: type):
        if not isinstance(default, t):
            raise ValueError("Parameter {default=} does not match type {t=}")
        super().__init__(name, help_str, default)
        self.arguments[ArgKey.type] = t

    def toml_valid(self, value: Any) -> bool:
        if not (t := self.arguments.get(ArgKey.type)):
            raise RuntimeError("'argument_args' does not contain 'type' (but it should)")
        return isinstance(value, t)


class BoolOption(BasicOption):

    def __init__(self, name: str, help_str: str, default: bool = False):
        super().__init__(name, help_str, default)
        self.arguments[ArgKey.action] = "store_true"

    def toml_valid(self, value: Any) -> bool:
        if value not in (True, False):
            return False
        return True


class NArgOption(BasicOption):

    def __init__(self, name: str, help_str: str, default: list[Any] | None = None):
        d = [] if default is None else default
        super().__init__(name, help_str, d)
        self.arguments[ArgKey.nargs] = '+'

    def toml_valid(self, value: Any) -> bool:
        return isinstance(value, list)
