import os.path
import validators
from os import makedirs
from typing import NewType, Tuple, Final, Any

vlevel: int = -1
URL = NewType('URL', str)

Context = NewType('Context', Tuple[int, str])
nocontext: Final[Context] = Context((-1, ""))


def while_context(context: Context) -> Context:
    tmp = context[1]
    tmp = "While " + tmp[0].lower() + tmp[1:] + ":"
    return Context((context[0], tmp))


# level 0 -> silent
# level 1 -> errors
# level 2 -> proceedings
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


def ensure_existence_dir(*pathelements: str) -> str:
    path = os.path.join(*pathelements)
    if path.startswith("~"):
        path = os.path.expanduser(path)
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        dprint(4, "Creating directory:", path)
    makedirs(path, exist_ok=True)
    return path


def ensure_existence_file(filename: str, *pathelements: str) -> str:
    path = os.path.join(ensure_existence_dir(*pathelements), filename)
    if not os.path.isfile(path):
        dprint(4, "Creating file:", path)
        with open(path, 'w') as file:
            pass
    return path


def read_files(*paths: str) -> list[str]:
    lines = []
    for path in paths:
        path = os.path.expanduser(path)
        path = os.path.realpath(path)
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
