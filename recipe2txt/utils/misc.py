import os.path
import sys
import traceback
import urllib.parse
from copy import deepcopy
from os import linesep
import validators
from recipe2txt.utils.ContextLogger import get_logger, DO_NOT_LOG
from typing import NewType, Any, TypeGuard, Optional
from pathlib import Path

__all__ = ["URL", "is_url", "File", "is_file", "Directory", "is_dir", "full_path", "ensure_existence_dir",
           "ensure_existence_dir_critical", "ensure_accessible_file", "ensure_accessible_file_critical",
           "read_files", "Counts", "dict2str", "head_str", "extract_urls", "get_shared_frames", "format_stacks"]

logger = get_logger(__name__)

URL = NewType('URL', str)


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
                reconstructed = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
                url = reconstructed if is_url(reconstructed) else url

                if url in processed:
                    logger.warning("%s already queued", url)
                else:
                    processed.add(url)
                    logger.info("Queued %s", url)
            else:
                logger.debug("Not an URL: %s", tmp)
    return processed


File = NewType('File', Path)


def is_file(value: Path) -> TypeGuard[File]:
    return value.is_file()


Directory = NewType('Directory', Path)


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


def _ensure_existence_dir(path: Path) -> tuple[Optional[Directory], tuple[str, Any, Any]]:
    if not is_dir(path):
        try:
            logger.info("Creating directory: %s", path)
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return None, ("Directory could not be created: %s (%s)", path, getattr(e, 'message', repr(e)))
    return Directory(path), (DO_NOT_LOG, "", "")


def ensure_existence_dir(*path_elem: str | Path) -> Optional[Directory]:
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


def _ensure_accessible_file(path: Path) -> tuple[Optional[File], tuple[str, Any, Any]]:
    if not is_file(path):
        directory, msg = _ensure_existence_dir(path.parents[0])
        if directory:
            try:
                logger.info("Creating file: %s", path)
                path.touch()
            except OSError as e:
                return None, ("File could not be created: %s (%s)", path, getattr(e, 'message', repr(e)))
        else:
            return None, msg
    with path.open("r") as f:
        if not f.readable():
            return None, ("File cannot be read: %s%s", path, "")
    with path.open("a") as f:
        if not f.writable():
            return None, ("File is not writable: %s%s", path, "")
    return File(path), (DO_NOT_LOG, "", "")


def ensure_accessible_file(*path_elem: str | Path) -> Optional[File]:
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
                lines += [line for line in file.readlines()]
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
        s = linesep.join(["[Absolute|Percentage of count above]", "",
                          "Total number of strings: {}",
                          "Identified as URLs: [{}|{:.2f}%]",
                          "URLs not yet (fully) saved: [{}|{:.2f}%]",
                          "URLs reached: [{}|{:.2f}%]",
                          "Recipes parsed partially: [{}|{:.2f}%]",
                          "Recipes parsed fully: [{}|{:.2f}%]", ""]) \
            .format(self.strings,
                    self.urls, (self.urls / self.strings) * 100,
                    self.require_fetching, (self.require_fetching / self.urls) * 100,
                    self.reached, (self.reached / self.urls) * 100,
                    self.parsed_partially, (self.parsed_partially / self.urls) * 100,
                    self.parsed_successfully, (self.parsed_successfully / self.urls) * 100
                    )
        return s


def dict2str(dictionary: dict[Any, Any]) -> str:
    items = ["{}: {}".format(*item) for item in dictionary.items()]
    return linesep.join(items)


def head_str(o: Any, max_length: int = 50) -> str:
    s = str(o)
    if len(s) > max_length:
        s = s[:max_length - 3].rstrip() + "..."
    return s.replace(linesep, " ")


def anonymize_paths(stack: traceback.StackSummary, first_visible_dir:str) -> traceback.StackSummary:
    for frame in stack:
        tmp = frame.filename.split(first_visible_dir, 1)
        if len(tmp) == 1:
            remaining_path = os.path.split(tmp[0])[1] # Just the filename
            frame.filename = os.path.join("...", remaining_path)
        else:
            remaining_path = tmp[1]
            if remaining_path.startswith("/"):
                remaining_path = remaining_path[1:]
            frame.filename = os.path.join("...", first_visible_dir, remaining_path)
    return stack


def get_shared_frames(tb_exes: list[traceback.TracebackException]) -> traceback.StackSummary:
    stacks = [tb_ex.stack for tb_ex in tb_exes]
    shortest = deepcopy(min(stacks, key=len))
    equal = True
    shared_list = []
    for i in range(len(shortest)):
        comp = stacks[0][i]
        for stack in stacks[1:]:
            if stack[i] != comp:
                equal = False
                break
        if not equal:
            i = i - 1 if i > 0 else i
            shared_list = shortest[:i]
            break
    if equal:
        shared_list = shortest[:-1]
    shared = traceback.StackSummary.from_list(shared_list)
    return shared


def format_stacks(tb_exes: list[traceback.TracebackException],
                  shared_stack: traceback.StackSummary,
                  first_visible_dir:Optional[str] = None) -> list[list[str]]:
    shared_stack_len = len(shared_stack)
    tb_exes_copy = deepcopy(tb_exes)
    for tb_ex in tb_exes_copy:
        tb_ex.stack = traceback.StackSummary.from_list(tb_ex.stack[shared_stack_len:])
        if first_visible_dir:
            tb_ex.stack = anonymize_paths(tb_ex.stack, first_visible_dir)
    if first_visible_dir:
        shared_stack = anonymize_paths(shared_stack, first_visible_dir)
    first_stack = shared_stack.format() + list(tb_exes_copy[0].format())[1:]

    sep = ["\t..." + linesep] if shared_stack else []
    stacks = [sep + list(tb_ex.format())[1:] for tb_ex in tb_exes_copy[1:]]

    return [first_stack] + stacks
