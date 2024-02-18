# Copyright (C) 2024 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt. If not, see <https://www.gnu.org/licenses/>.
import re
import urllib.parse
from os import linesep
from types import ModuleType
from typing import Any, Final, NewType, TypeGuard

import validators

from recipe2txt.utils.ContextLogger import get_logger

__all__ = [
    "NEVER_CATCH",
    "URL",
    "is_url",
    "extract_urls",
    "Counts",
    "dict2str",
    "head_str",
    "obj2sql_str",
    "get_all_dict",
]

logger = get_logger(__name__)

NEVER_CATCH: Final = (SystemExit, MemoryError, KeyboardInterrupt)

URL = NewType("URL", str)


def is_url(value: str) -> TypeGuard[URL]:
    return bool(validators.url(value))


def extract_urls(lines: list[str]) -> set[URL]:
    processed: set[URL] = set()
    for line in lines:
        strings = line.split()
        for string in strings:
            tmp = string
            if not string.startswith("http"):
                string = "http://" + string
            if is_url(string):
                url = string

                # Strip variables to avoid duplicating urls
                parsed = urllib.parse.urlparse(url)
                reconstructed = urllib.parse.urlunparse(
                    (parsed.scheme, parsed.netloc, parsed.path, "", "", "")
                )
                url = reconstructed if is_url(reconstructed) else url

                if url in processed:
                    logger.warning("%s already queued", url)
                else:
                    processed.add(url)
                    logger.info("Queued %s", url)
            else:
                logger.debug("Not an URL: %s", tmp)
    return processed


class Counts:

    def __init__(self) -> None:
        self.strings: int = 0
        self.urls: int = 0
        self.require_fetching: int = 0
        self.reached: int = 0
        self.parsed_successfully: int = 0
        self.parsed_partially: int = 0

    def __str__(self) -> str:
        s = linesep.join(
            [
                "[Absolute|Percentage of count above]",
                "",
                "Total number of strings: {}",
                "Identified as URLs: [{}|{:.2f}%]",
                "URLs not yet (fully) saved: [{}|{:.2f}%]",
                "URLs reached: [{}|{:.2f}%]",
                "Recipes parsed partially: [{}|{:.2f}%]",
                "Recipes parsed fully: [{}|{:.2f}%]",
                "",
            ]
        ).format(
            self.strings,
            self.urls,
            (self.urls / self.strings) * 100,
            self.require_fetching,
            (self.require_fetching / self.urls) * 100,
            self.reached,
            (self.reached / self.urls) * 100,
            self.parsed_partially,
            (self.parsed_partially / self.urls) * 100,
            self.parsed_successfully,
            (self.parsed_successfully / self.urls) * 100,
        )
        return s


def dict2str(dictionary: dict[Any, Any], sep: str = linesep) -> str:
    items = [f"{item[0]}: {item[1]}" for item in dictionary.items()]
    return sep.join(items)


def head_str(o: Any, max_length: int = 50) -> str:
    s = str(o)
    if len(s) > max_length:
        s = s[: max_length - 3].rstrip() + "..."
    return s.replace(linesep, " ")


_ONLY_ALPHANUM_DOT_UNDERSCORE: Final = re.compile(r"^[\w_\.]+$")


def _sanitize(value: object) -> str:
    string = str(value)
    matches = _ONLY_ALPHANUM_DOT_UNDERSCORE.findall(string)
    if len(matches) == 0:
        raise ValueError(
            "Strings used as identifiers in SQL-statements for this application"
            " are only allowed to contain alphanumeric characters, dots and underscores"
            f" (offending string : '{string}')"
        )
    if len(matches) > 1:
        raise RuntimeError("This should not be possible")
    return f'"{string}"'


def obj2sql_str(*values: object) -> str:
    """
    Function preventing SQL-injection attacks from arbitrary values.

    Since inserting arbitrary values into SQL-queries can lead to a SQL-injection
    attack, this function disallows anything but alphanumeric characters, dots and
    underscores.

    Additionally, it wraps each string into double-quotes. This prevents SQLite
    from executing any SQL-statement hidden inside the quotes, since the contained
    characters can only be treated as strings and never as part of the statement.

    Args:
        *values (): One or more values

    Returns:
        'STRING' -> '"STRING"'
        'STRING1', 'STRING2', 'STRING3' -> '"STRING1", "STRING2", "STRING3"'
        'String_2' -> '"String_2"'
        'String 2' -> RuntimeError
        '); DROP TABLE recipes' -> RuntimeError

    Raises:
        RuntimeError: If characters other than alphanumeric ASCII-characters and
            underscores are detected in strings.

    """
    sanitized = [_sanitize(value) for value in values]
    return ", ".join(sanitized)


def get_all_dict(mod: ModuleType) -> dict[str, Any]:
    """
    Builds a dictionary from the __all__-attribute of mod.

    The keys are the strings in __all__ and the values are references to the
    corresponding module-members (e.g. the functions, classes, variables declared in
    that module)

    Args:
        mod (): A python module

    Returns:
        A dictionary filled with member-name|member-reference pairs or an empty
        dictionary if the module does not declare __all__

    """
    if not (declared_items := mod.__dict__["__all__"]):
        return {}
    return {name: mod.__dict__[name] for name in declared_items}
