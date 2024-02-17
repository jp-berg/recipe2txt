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
import os
import os.path
import re
import sqlite3
import sys
import urllib.parse
from os import linesep
from pathlib import Path
from time import localtime, strftime
from types import ModuleType
from typing import Any, Final, NewType, TypeGuard

import validators

from recipe2txt.utils.ContextLogger import DO_NOT_LOG, get_logger

__all__ = [
    "NEVER_CATCH",
    "URL",
    "is_url",
    "extract_urls",
    "File",
    "real_file",
    "Directory",
    "real_dir",
    "AccessibleDatabase",
    "is_accessible_db",
    "full_path",
    "ensure_existence_dir",
    "ensure_existence_dir_critical",
    "create_timestamped_dir",
    "ensure_accessible_file",
    "ensure_accessible_file_critical",
    "ensure_accessible_db_critical",
    "read_files",
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


File = NewType("File", Path)


def real_file(value: Path) -> TypeGuard[File]:
    return value.is_file()


Directory = NewType("Directory", Path)


def real_dir(value: Path) -> TypeGuard[Directory]:
    return value.is_dir()


AccessibleDatabase = NewType("AccessibleDatabase", Path)
"""Type representing a database file, that was (at one point during program 
execution) a valid and accessible
Sqlite3-database"""


def is_accessible_db(path: Path) -> TypeGuard[AccessibleDatabase]:
    """Checks if the file 'path' points to is an :py:data:`AccessibleDatabase`"""
    try:
        con = sqlite3.connect(path)
    except sqlite3.OperationalError:
        return False
    cur = con.cursor()

    try:
        cur.execute("PRAGMA SCHEMA_VERSION")
    except sqlite3.DatabaseError:
        return False
    finally:
        cur.close()
        con.close()
    return True


def full_path(*pathelements: str | Path) -> Path:
    first = str(pathelements[0]).lstrip()
    last = str(pathelements[-1]).rstrip() if len(pathelements) > 1 else ""

    path = Path(first, *pathelements[1:-1], last)
    path = path.expanduser()
    path = Path(os.path.expandvars(path))
    path = path.resolve()
    return path


def _ensure_existence_dir(
    path: Path,
) -> tuple[Directory | None, tuple[str, Any] | tuple[str, Any, Any]]:
    try:
        if path.is_file():
            return None, (
                (
                    "%s is already a file, thus a directory with the same name cannot"
                    " exist"
                ),
                path,
            )
        exists = real_dir(path)
    except OSError as e:
        return None, (
            "Directory cannot be accessed: %s (%s)",
            path,
            getattr(e, "message", repr(e)),
        )
    if not exists:
        try:
            logger.info("Creating directory: %s", path)
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return None, (
                "Directory could not be created: %s (%s)",
                path,
                getattr(e, "message", repr(e)),
            )
    return Directory(path), (DO_NOT_LOG, "", "")


def ensure_existence_dir(*path_elem: str | Path) -> Directory | None:
    path = full_path(*path_elem)
    directory, msg = _ensure_existence_dir(path)
    if not directory:
        if msg:
            logger.error(*msg)
    return directory


def ensure_existence_dir_critical(*path_elem: str | Path) -> Directory:
    path = full_path(*path_elem)
    directory, msg = _ensure_existence_dir(path)
    if not directory:
        logger.critical(*msg)
        sys.exit(os.EX_IOERR)
    return directory


def create_timestamped_dir(*path_elem: str | Path, name: str = "") -> Directory | None:
    current_time = strftime("%Y-%m-%d_%H-%M-%S", localtime())
    parent = ensure_existence_dir(*path_elem)
    if not parent:
        return None
    dir_name = f"{name}__{current_time}" if name else current_time
    i = 1
    tmp = parent / dir_name
    while tmp.is_dir():
        tmp.with_stem(f"{tmp.stem}--{i}")
        i += 1
    directory = tmp
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _ensure_accessible_file(
    path: Path,
) -> tuple[File | None, tuple[str, Any] | tuple[str, Any, Any]]:
    try:
        if path.is_dir():
            return None, (
                (
                    "%s is already a directory, thus a file with the same name cannot"
                    " exist"
                ),
                path,
            )
        exists = path.is_file()
    except OSError as e:
        return None, (
            "File cannot be accessed: %s (%s)",
            path,
            getattr(e, "message", repr(e)),
        )
    if not exists:
        directory, msg = _ensure_existence_dir(path.parent)
        if directory:
            try:
                logger.info("Creating file: %s", path)
                path.touch()
            except OSError as e:
                return None, (
                    "File could not be created: %s (%s)",
                    path,
                    getattr(e, "message", repr(e)),
                )
        else:
            return None, msg
    with path.open("r") as f:
        if not f.readable():
            return None, ("File cannot be read: %s", path)
    with path.open("a") as f:
        if not f.writable():
            return None, ("File is not writable: %s", path)
    return File(path), (DO_NOT_LOG, "", "")


def ensure_accessible_file(*path_elem: str | Path) -> File | None:
    path = full_path(*path_elem)
    file, msg = _ensure_accessible_file(path)
    if not file:
        logger.error(*msg)
    return file


def ensure_accessible_file_critical(*path_elem: str | Path) -> File:
    path = full_path(*path_elem)
    file, msg = _ensure_accessible_file(path)
    if not file:
        logger.critical(*msg)
        sys.exit(os.EX_IOERR)
    return file


def ensure_accessible_db_critical(*path_elem: str | Path) -> AccessibleDatabase:
    """
    Tries to find (or create if not existing) a valid database file from the path
    elements provided.

    Works like :py:function:`recipe2txt.utils.misc.ensure_accessible_file_critical`.
    Args:
        *path_elem: The elements from which a path should be constructed
    Returns:
        A path to a valid Sqlite3-database-file, which is accessible by this program
    Raises:
        SystemExit: If the database-file cannot be created.

    """
    db_path = full_path(*path_elem)
    ensure_existence_dir_critical(db_path.parent)
    if is_accessible_db(db_path):
        db_file = db_path
    else:
        logger.critical("Database not accessible: %s", db_path)
        sys.exit(os.EX_IOERR)
    return db_file


def read_files(*possible_paths: str | Path) -> list[str]:
    lines = []
    for p in possible_paths:
        path = full_path(p)
        if path.is_file():
            logger.info("Reading %s", path)
            path.read_text()
            with path.open("r") as file:
                lines += list(file.readlines())
        else:
            logger.error("Not a file: %s", path)
    return lines


class Counts:
    def __init__(self) -> None:
        self.strings: int = 0
        self.urls: int = 0
        self.require_fetching: int = 0
        self.reached: int = 0
        self.parsed_successfully: int = 0
        self.parsed_partially: int = 0

    def __str__(self) -> str:
        s = linesep.join([
            "[Absolute|Percentage of count above]",
            "",
            "Total number of strings: {}",
            "Identified as URLs: [{}|{:.2f}%]",
            "URLs not yet (fully) saved: [{}|{:.2f}%]",
            "URLs reached: [{}|{:.2f}%]",
            "Recipes parsed partially: [{}|{:.2f}%]",
            "Recipes parsed fully: [{}|{:.2f}%]",
            "",
        ]).format(
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
