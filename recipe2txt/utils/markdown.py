import re
from typing import Pattern, Final, Optional
from os import linesep

__all__ = ["EMPTY_COMMENT", "esc", "header", "quote", "italic", "bold", "s_th", "super", "code", "codeblock",
           "page_sep", "link", "section_link", "unordered", "ordered", "table", "paragraph"]


indent: Final[str] = " " * 4

"""matches all characters in the second capture group if they are not lead by a '\' (negative lookbehind)"""
not_escaped: Final[Pattern] = re.compile(r"(?<!\\)(`|\*|_|{|}|\[|\]|\(|\)|#|\+|-|\.|!|~~)")
EMPTY_COMMENT: Final[str] = "\n<!-- -->\n" # Helpful to terminate lists in case two different lists follow each other


def esc(string: str) -> str:
    """
    escapable symbols: \'*_{}[]()#+-.!
    replace first capture group with '\':
    """
    return not_escaped.sub(r"\\\1", string)


def header(string: str, level: int = 1) -> str:
    if level < 1:
        level = 1
    elif level > 6:
        level = 6

    return "#" * level + " " + string


def quote(string: str) -> str:
    return "> " + string


def italic(string: str) -> str:
    return "_" + str.strip(string) + "_"


def bold(string: str) -> str:
    return "**" + str.strip(string) + "**"


def s_th(string: str) -> str:
    return "~~" + string + "~~"


def super(base: str, exp: str) -> str:
    return base.rstrip() + "^" + exp.lstrip()


def code(string: str) -> str:
    return "`" + string + "`"


def codeblock(string: str, language: str = "") -> str:
    return "```" + language + linesep + string + linesep + "```"


def page_sep() -> str:
    return linesep + "---" + linesep


def link(url: str, description: Optional[str] = None) -> str:
    if not description:
        description = url
    return "".join(["[", description, "](", url, ")"])


def section_link(header: str, description: Optional[str] = None) -> str:
    ref = "#" + header.replace(" ", "-")
    if not description:
        description = header
    return link(ref, description)


def _indent(level: int) -> str:
    if level < 0:
        level = 0
    elif level > 6:
        level = 6
    return level * indent


def unordered(*items: str, level: int = 0) -> str:
    pre = _indent(level) + "* "
    return pre + (linesep + pre).join(items) + linesep


def ordered(*items: str, level: int = 0, start: int = 1) -> str:
    pre = _indent(level)
    res = ""
    for item in items:
        res += pre + str(start) + ". " + item + linesep
        start += 1
    return res


def _construct_row(l: list[str]) -> str:
    return "|" + "|".join(l) + "|" + linesep


def table(lists: list[list[str]]) -> str:
    if len(lists) == 0: return ""
    maxlen = len(lists[0])
    for l in lists[1:]:
        if len(l) > maxlen:
            raise ValueError("Length of one sublist is longer than the header list (first sublist)")

    res = ""
    res += _construct_row(lists[0])  # header
    res += "|" + "---|" * maxlen + linesep  # divider
    for l in lists[1:]: res += _construct_row(l)
    return res


def paragraph() -> str:
    return linesep * 2