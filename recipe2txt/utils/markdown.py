# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.

import hashlib
import re
from os import linesep
from typing import Final, Optional, Pattern

from recipe2txt.utils.conditional_imports import LiteralString

__all__ = ["EMPTY_COMMENT", "esc", "header", "quote", "italic", "bold", "s_th", "superscript", "code", "codeblock",
           "page_sep", "link", "section_link", "unordered", "ordered", "table", "paragraph"]


indent: Final = " " * 4

"""matches all characters in the second capture group if they are not lead by a '\' (negative lookbehind)"""
NOT_ESCAPED: Final[Pattern[str]] = re.compile(r"(?<!\\)(`|\*|_|{|}|\[|\]|\(|\)|#|\+|-|\.|!|~~)")
# Helpful to terminate lists in case two different lists follow each other
EMPTY_COMMENT: Final = "\n<!-- -->\n"


def fragmentify(string: str) -> str:
    return hashlib.sha1(string.encode("utf-8")).hexdigest()


def esc(string: str) -> str:
    """
    escapable symbols: \'*_{}[]()#+-.!
    replace first capture group with '\':
    """
    return NOT_ESCAPED.sub(r"\\\1", string)


def header(string: str, level: int = 1, fragmentified_section_link: bool = False) -> str:
    if level < 1:
        level = 1
    elif level > 6:
        level = 6
    if fragmentified_section_link:
        f = fragmentify(string)
        pre = f"<div id=\"{f}\"></div>{linesep*2}"
    else:
        pre = ""
    return pre + "#" * level + " " + string


def quote(string: str) -> str:
    return "> " + string


def italic(string: str) -> str:
    return "_" + str.strip(string) + "_"


def bold(string: str) -> str:
    return "**" + str.strip(string) + "**"


def s_th(string: str) -> str:
    return "~~" + string + "~~"


def superscript(base: str, exp: str) -> str:
    return base.rstrip() + "^" + exp.lstrip()


def code(string: str) -> str:
    return "`" + string + "`"


def codeblock(*strings: str, language: str = "") -> list[str]:
    return ["```" + language + linesep*2, *strings , linesep*2 + "```"]


def page_sep() -> str:
    return linesep + "---" + linesep


def link(url: str, description: str | None = None) -> str:
    if not description:
        description = url
    return f"[{description}]({url})"


def section_link(header: str, description: str | None = None, fragmentified: bool = False) -> str:
    if fragmentified:
        ref = "#" + fragmentify(header)
    else:
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


def unordered(*items: str, level: int = 0) -> list[str]:
    local_indent = _indent(level)
    return [f"{local_indent}* {item}{linesep}" for item in items]


def ordered(*items: str, level: int = 0, start: int = 1) -> list[str]:
    pre = _indent(level)
    return [f"{pre}{number}. {item}{linesep}" for number, item in enumerate(items, start)]


def _construct_row(l: list[str]) -> str:
    return "|" + "|".join(l) + "|" + linesep


def table(lists: list[list[str]]) -> list[str]:
    if len(lists) == 0:
        return []
    maxlen = len(lists[0])
    for sublist in lists[1:]:
        if len(sublist) > maxlen:
            raise ValueError("Length of one sublist is longer than the header list (first sublist)")

    head = [_construct_row(lists[0]), "|" + "---|" * maxlen + linesep]  # header, divider
    body = [_construct_row(sublist) for sublist in lists[1:]]
    return head + body


def paragraph() -> str:
    return linesep * 2
