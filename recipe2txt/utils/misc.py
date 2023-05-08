import os.path
import sys
import traceback
import validators
from os import makedirs, linesep
from typing import NewType, Tuple, Final, Any, TypeGuard, Optional

__all__ = ["set_vlevel", "URL", "is_url", "File", "is_file",
           "Context", "nocontext", "while_context", "dprint",
           "full_path", "ensure_existence_dir", "ensure_accessible_file", "ensure_accessible_file_critical",
           "read_files", "Counts", "cutoff", "dict2str", "head_str", "mark_stage"]
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
def dprint(level: int, *args: str, sep: str = ' ', end: str = linesep, file: Any = None, flush: bool = False,
           context: Context = nocontext) -> Context:
    assert vlevel != -1
    if level <= vlevel:
        if context[0] > vlevel:
            print(context[1], file=file, flush=flush, end=end)
        print(*args, sep=sep, end=end, file=file, flush=flush)
    return Context((level, sep.join(args)))


def mark_stage(name: str) -> None:
    dprint(3, linesep, "---", name, "---", linesep)


def full_path(*pathelements: str) -> str:
    path = os.path.join(*pathelements)
    path = path.strip()
    if path.startswith("~"): path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.realpath(path)
    return path


def ensure_existence_dir(*pathelements: str) -> Optional[str]:
    path = full_path(*pathelements)
    if not os.path.isdir(path):
        try:
            dprint(4, "Creating directory:", path)
            makedirs(path, exist_ok=True)
        except OSError:
            return None
    return path


def ensure_accessible_file(filename: str, *pathelements: str) -> Optional[File]:
    if dirpath := ensure_existence_dir(*pathelements):
        path = os.path.join(dirpath, filename)
    else:
        return None
    try:
        with open(path, 'a'):
            pass
    except OSError:
        return None
    return File(path)


def ensure_accessible_file_critical(filename: str, *pathelements: str) -> File:
    try:
        path = full_path(*pathelements)
        os.makedirs(path, exist_ok=True)
        path = os.path.join(path, filename)
        with open(path, 'a'):
            pass

    except OSError as e:
        print("Error while creating or accessing file {}: {}"
              .format(full_path(full_path(*pathelements, filename)), getattr(e, 'message', repr(e))),
              file=sys.stderr)
        exception_trace = "".join(traceback.format_exception(e))
        dprint(4, exception_trace, file=sys.stderr)
        exit(os.EX_IOERR)
    return File(path)


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


def cutoff(url: URL, *identifiers: str) -> URL:
    for i in identifiers:
        start_tracking_part = url.find(i)
        if start_tracking_part > -1:
            tmp = url[:start_tracking_part]
            if is_url(tmp):
                url = tmp
    return url


def dict2str(dictionary: dict) -> str:
    items = ["{}: {}".format(*item) for item in dictionary.items()]
    return linesep.join(items)


def head_str(o: Any, max_length: int = 50) -> str:
    s = str(o)
    if len(s) > max_length:
        s = s[:max_length - 3].rstrip() + "..."
    return s.replace(linesep, " ")
