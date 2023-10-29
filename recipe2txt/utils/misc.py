# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.

import os.path
import sys
import urllib.parse
from os import linesep
from pathlib import Path
from time import localtime, strftime
from typing import Any, NewType, TypeGuard

import validators

from recipe2txt.utils.ContextLogger import DO_NOT_LOG, get_logger

__all__ = [
    "URL",
    "is_url",
    "extract_urls",
    "File",
    "is_file",
    "Directory",
    "is_dir",
    "full_path",
    "ensure_existence_dir",
    "ensure_existence_dir_critical",
    "create_timestamped_dir",
    "ensure_accessible_file",
    "ensure_accessible_file_critical",
    "read_files",
    "Counts",
    "dict2str",
    "head_str",
]

logger = get_logger(__name__)

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


def is_file(value: Path) -> TypeGuard[File]:
    return value.is_file()


Directory = NewType("Directory", Path)


def is_dir(value: Path) -> TypeGuard[Directory]:
    return value.is_dir()


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
        exists = is_dir(path)
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
    items = ["{}: {}".format(*item) for item in dictionary.items()]
    return sep.join(items)


def head_str(o: Any, max_length: int = 50) -> str:
    s = str(o)
    if len(s) > max_length:
        s = s[: max_length - 3].rstrip() + "..."
    return s.replace(linesep, " ")
