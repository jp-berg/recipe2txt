import logging
import os.path
import sys
import traceback
import urllib.parse
from copy import deepcopy
from os import makedirs, linesep
import validators
from recipe2txt.utils.ContextLogger import get_logger
from typing import NewType, Any, TypeGuard, Optional

__all__ = ["URL", "is_url", "File", "is_file", "Directory", "is_dir", "full_path", "ensure_existence_dir",
           "ensure_accessible_file", "ensure_accessible_file_critical", "read_files", "Counts", "dict2str",
           "head_str", "extract_urls", "get_shared_frames", "format_stacks"]

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


File = NewType('File', str)


def is_file(value: str) -> TypeGuard[File]:
    return os.path.isfile(value)


Directory = NewType('Directory', str)


def is_dir(value: str) -> TypeGuard[Directory]:
    return os.path.isdir(value)


def full_path(*pathelements: str) -> str:
    path = os.path.join(*pathelements)
    path = path.strip()
    if path.startswith("~"): path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.realpath(path)
    return path


def ensure_existence_dir(*pathelements: str) -> Optional[Directory]:
    path = full_path(*pathelements)
    if not is_dir(path):
        try:
            logger.info("Creating directory: %s", path)
            makedirs(path, exist_ok=True)
        except OSError:
            return None

    return Directory(path)


def ensure_accessible_file(filename: str, directory: Optional[Directory] = None) -> Optional[File]:
    filepath = os.path.join(directory, filename) if directory else filename
    try:
        with open(filepath, 'a'):
            pass
    except OSError:
        return None
    return File(filepath)


def ensure_accessible_file_critical(filename: str, directory: Optional[Directory] = None) -> File:
    try:
        filepath = os.path.join(directory, filename) if directory else filename
        with open(filepath, 'a'):
            pass

    except OSError as e:
        print("Error while creating or accessing file {}: {}"
              .format(full_path(full_path(filepath)), getattr(e, 'message', repr(e))),
              file=sys.stderr)
        if logger.isEnabledFor(logging.DEBUG):
            exception_trace = "".join(traceback.format_exception(e))
            logger.debug(exception_trace)
        sys.exit(os.EX_IOERR)
    return File(filepath)


def read_files(*paths: str) -> list[str]:
    lines = []
    for path in paths:
        path = full_path(path)
        if os.path.isfile(path):
            logger.info("Reading %s", path)
            with open(path, 'r') as file:
                for line in file.readlines():
                    lines.append(line)
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
