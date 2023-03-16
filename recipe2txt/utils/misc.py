import os.path
import sys
import traceback
import validators
from os import makedirs
from typing import NewType, Tuple, Final, Any, TypeGuard

__all__ = ["set_vlevel", "URL", "is_url", "File", "is_file",
           "Context", "nocontext", "while_context", "dprint",
           "full_path", "ensure_existence_dir", "ensure_accessible_file", "ensure_accessible_file_critical",
           "read_files", "Counts", "cutoff"]
vlevel: int = -1


def set_vlevel(level: int) -> None:
    if level < 0: level = 0
    global vlevel
    vlevel = level


URL = NewType('URL', str)


def is_url(value: str) -> TypeGuard[URL]:
    if validators.url(value):
        return True
    else:
        return False


File = NewType('File', str)


def is_file(value: str) -> TypeGuard[File]:
    return os.path.isfile(value)


Context = NewType('Context', Tuple[int, str])
nocontext: Final[Context] = Context((-1, ""))


def while_context(context: Context) -> Context:
    tmp = context[1]
    tmp = "While " + tmp[0].lower() + tmp[1:] + ":"
    return Context((context[0], tmp))


# level 0 -> silent
# level 1 -> errors
# level 2 -> warnings
# level 3 -> notice
# level 4 -> all
def dprint(level: int, *args: str, sep: str = ' ', end: str = '\n', file: Any = None, flush: bool = False,
           context: Context = nocontext) -> Context:
    assert vlevel != -1
    if level <= vlevel:
        if context[0] > vlevel:
            print(context[1], file=file, flush=flush, end=end)
        print(*args, sep=sep, end=end, file=file, flush=flush)
    return Context((level, sep.join(args)))


def full_path(*pathelements: str) -> str:
    path = os.path.join(*pathelements)
    if path.startswith("~"): path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.realpath(path)
    return path


def ensure_existence_dir(*pathelements: str) -> str:
    path = full_path(*pathelements)
    if not os.path.isdir(path):
        dprint(4, "Creating directory:", path)
        makedirs(path, exist_ok=True)
    return path


def ensure_accessible_file(filename: str, *pathelements: str) -> File:
    path = os.path.join(ensure_existence_dir(*pathelements), filename)
    with open(path, 'a') as file:
        pass
    return File(path)


def ensure_accessible_file_critical(filename: str, *pathelements: str) -> File:
    try:
        path = ensure_accessible_file(filename, *pathelements)
    except OSError as e:
        print("Error while creating or accessing file {}: {}"
              .format(full_path(full_path(*pathelements, filename)), getattr(e, 'message', repr(e))),
              file=sys.stderr)
        exception_trace = "".join(traceback.format_exception(e))
        dprint(4, exception_trace, file=sys.stderr)
        exit(os.EX_IOERR)
    return path


def read_files(*paths: str) -> list[str]:
    lines = []
    for path in paths:
        path = full_path(path)
        if os.path.isfile(path):
            dprint(4, "Reading", path)
            with open(path, 'r') as file:
                for line in file.readlines():
                    lines.append(line)
        else:
            dprint(1, "Not a file:", path)
    return lines


class Counts:
    def __init__(self) -> None:
        self.strings: int = 0
        self.urls: int = 0
        self.reached: int = 0
        self.parsed_successfully: int = 0
        self.parsed_partially: int = 0

    def __str__(self) -> str:
        return """
            \t [Absolute|Percentage of count above]
            Total number of strings: {}
            Identified as URLs: [{}|{:.2f}%]
            URLs reached: [{}|{:.2f}%]
            Recipes parsed partially: [{}|{:.2f}%]
            Recipes parsed fully: [{}|{:.2f}%]
            """.format(
            self.strings,
            self.urls, (self.urls / self.strings) * 100,
            self.reached, (self.reached / self.urls) * 100,
            self.parsed_partially, (self.parsed_partially / self.urls) * 100,
            self.parsed_successfully, (self.parsed_successfully / self.urls) * 100
        )


def cutoff(url: URL, *identifiers: str) -> URL:
    for i in identifiers:
        start_tracking_part = url.find(i)
        if start_tracking_part > -1:
            tmp = url[:start_tracking_part]
            if validators.url(tmp):
                url = URL(tmp)
    return url
