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

import logging
import os
import urllib.request
from pathlib import Path
from typing import Final

import recipe_scrapers

import recipe2txt.html2recipe as h2r
from recipe2txt.utils.conditional_imports import StrEnum
from recipe2txt.utils.ContextLogger import QueueContextManager as QCM
from recipe2txt.utils.ContextLogger import (
    disable_loggers,
    get_logger,
    root_log_setup,
    suppress_logging,
)
from recipe2txt.utils.markdown import *
from recipe2txt.utils.misc import (
    NEVER_CATCH,
    URL,
    Directory,
    File,
    ensure_accessible_file_critical,
    is_url,
)

__all__ = [
    "HTML_LIST",
    "HTML_BAD",
    "RECIPE_LIST",
    "MD_LIST",
    "TXT_LIST",
    "URL_LIST",
    "FULL_TXT",
    "FULL_MD",
]

logger = get_logger(__name__)

if __name__ == "__main__":
    root_log_setup(logging.INFO)
else:
    disable_loggers()

ROOT: Final = Directory(Path(__file__).parent)


def get_urls() -> list[URL]:
    urls_file = ROOT / "URLs"
    txt = urls_file.read_text()
    urls = [line for line in txt.split(os.linesep) if line and is_url(line)]
    urls.sort()
    return urls


URL_LIST: Final[list[URL]] = get_urls()


class FileExtension(StrEnum):
    txt = ".txt"
    md = ".md"
    parsed = ".parsed"
    html = ".html"


def gen_full_path(filename: str, file_extension: FileExtension) -> File:
    f_e = f"{file_extension}"
    return ensure_accessible_file_critical(ROOT, f_e[1:], filename + f_e)


tmp_filenames = [url.rsplit(":", 1)[1] for url in URL_LIST if is_url(url)]
tmp_filenames.sort()
FILENAMES: Final[list[str]] = tmp_filenames


def fetch_url(url: URL, filename: File) -> bytes:
    if not filename.stat().st_size > 0:
        logger.info("Generating %s from %s", filename, url)
        html = urllib.request.urlopen(url).read()
        filename.write_bytes(html)
    else:
        logger.info("Already available: %s", filename)
        html = filename.read_bytes()
    return bytes(html)


def gen_html(filenames: list[str]) -> list[bytes]:
    html_paths = [gen_full_path(name, FileExtension.html) for name in filenames]
    html = [fetch_url(url, filename) for url, filename in zip(URL_LIST, html_paths)]
    return html


delim = "---"


def parse_html(filename: File, filename_parsed: File, url: URL) -> h2r.Recipe:
    html = filename.read_bytes()
    r = recipe_scrapers.scrape_html(html=html, org_url=url)  # type: ignore[arg-type]
    attributes = []
    with QCM(logger, logger.info, "Scraping %s", url):
        for method in h2r.METHODS:
            a = None
            try:
                a = getattr(r, method)()
            except NEVER_CATCH:
                raise
            except Exception:
                logger.error("%s not found", method)
            a = h2r.info2str(method, a)
            attributes.append(a)
        attributes += [url, str(int(h2r.gen_status(attributes))), h2r.SCRAPER_VERSION]
        recipe = h2r.Recipe(*attributes)  # type: ignore[arg-type]
    with filename_parsed.open("w") as file:
        for a in attributes:
            file.write(str(a))
            file.write(os.linesep + delim + os.linesep)
    return recipe


def parse_txt(path: File) -> h2r.Recipe:
    attributes = []
    tmp = []
    with path.open() as file:
        for line in file.readlines():
            line = line.rstrip(os.linesep)
            if line != delim:
                tmp.append(line)
            else:
                attributes.append(os.linesep.join(tmp))
                tmp.clear()
    if len(attributes) != len(h2r.RECIPE_ATTRIBUTES):
        raise ValueError("Error while parsing serialized recipes")
    t = tuple(attributes)
    t = h2r.int2status(t)
    recipe = h2r.Recipe(*t)  # type: ignore[arg-type]
    return recipe


def gen_parsed(filenames: list[str]) -> list[h2r.Recipe]:
    files_html = [gen_full_path(name, FileExtension.html) for name in filenames]
    files_parsed = [gen_full_path(name, FileExtension.parsed) for name in filenames]
    recipes = []

    for html, parsed, url in zip(files_html, files_parsed, URL_LIST):
        if not parsed.stat().st_size > 0:
            logger.info("Generating %s from %s", parsed, html)
            recipes.append(parse_html(html, parsed, url))
        else:
            logger.info("Already available: %s", parsed)
            recipes.append(parse_txt(parsed))
    return recipes


def re2md(recipe: h2r.Recipe) -> list[str]:
    title = recipe.title if recipe.title != h2r.NA else recipe.url
    title = esc(title)
    url = esc(recipe.url)
    host = None if recipe.host == h2r.NA else italic(esc(recipe.host))

    escaped = [esc(item) for item in recipe.ingredients.split(os.linesep)]
    ingredients = unordered(*escaped)

    escaped = [esc(step) for step in recipe.instructions.split(os.linesep)]
    instructions = ordered(*escaped)

    md = (
        [
            header(title, 2, True),
            paragraph(),
            recipe.total_time + " min | " + recipe.yields,
            paragraph(),
        ]
        + ingredients
        + [EMPTY_COMMENT]
        + instructions
        + [paragraph(), italic("from:"), " ", link(url, host), paragraph()]
    )

    return md


def re2txt(recipe: h2r.Recipe) -> list[str]:
    title = recipe.title if recipe.title != h2r.NA else recipe.url
    txt = [
        title,
        os.linesep * 2,
        recipe.total_time + " min | " + recipe.yields + os.linesep * 2,
        recipe.ingredients,
        os.linesep * 2,
        recipe.instructions.replace(os.linesep, os.linesep * 2),
        os.linesep * 2,
        "from: " + recipe.url,
        os.linesep * 5,
    ]
    return txt


def gen_formatted(filenames: list[str], file_extension: FileExtension) -> list[str]:
    if file_extension not in (FileExtension.md, FileExtension.txt):
        raise ValueError(f"{file_extension} is not a valid extension for this function")
    files_parsed = [gen_full_path(name, FileExtension.parsed) for name in filenames]
    files_formatted = [gen_full_path(name, file_extension) for name in filenames]
    formatted_recipes = []
    for parsed, formatted_file in zip(files_parsed, files_formatted):
        if not formatted_file.stat().st_size > 0:
            logger.info("Generating %s from %s", formatted_file, parsed)
            recipe = parse_txt(parsed)
            if file_extension is FileExtension.md:
                tmp_list = re2md(recipe)
            else:
                tmp_list = re2txt(recipe)
            formatted = "".join(tmp_list)
            formatted_file.write_text(formatted)
            formatted_recipes.append(formatted)
        else:
            logger.info("Already available: %s", formatted_file)
            formatted_recipes.append(formatted_file.read_text())
    return formatted_recipes


HTML_LIST: Final[list[bytes]] = gen_html(FILENAMES)
_BAD_URL: Final = "https://en.wikipedia.org/wiki/Recipe"
HTML_BAD: Final[tuple[str, bytes]] = (
    _BAD_URL,
    fetch_url(URL(_BAD_URL), gen_full_path("FAIL_RECIPE", FileExtension.html)),
)
RECIPE_LIST: Final[list[h2r.Recipe]] = gen_parsed(FILENAMES)
RECIPE_LIST.sort(key=lambda x: x.title)
MD_LIST: Final[list[str]] = gen_formatted(FILENAMES, FileExtension.md)
TXT_LIST: Final[list[str]] = gen_formatted(FILENAMES, FileExtension.txt)


def recipes2str(recipes: list[h2r.Recipe], markdown: bool = False) -> list[str]:
    lines = []
    if markdown:
        for recipe in recipes:
            lines += re2md(recipe)
    else:
        for recipe in recipes:
            lines += re2txt(recipe)

    if len(recipes) > 3:
        if markdown:
            titles_md_fmt = [
                f"{section_link(esc(recipe.title), fragmentified=True)} -"
                f" {esc(recipe.host)}{os.linesep}"
                for recipe in recipes
            ]
            titles = ordered(*titles_md_fmt)
        else:
            titles = [
                f"{recipe.title} - {recipe.host}{os.linesep}" for recipe in recipes
            ]
            titles = (
                [os.linesep]
                + titles
                + [paragraph(), ("-" * 10) + os.linesep * 2, paragraph()]
            )
    else:
        titles = []

    return titles + lines


class TestRecipeWriter:

    def __init__(self, out: File, markdown: bool):
        self.out = out
        self.markdown = markdown

    def write(self, recipes: list[h2r.Recipe]) -> str:
        lines = recipes2str(recipes, self.markdown)
        text = "".join(lines)
        self.out.write_text(text)
        return text


def gen_formatted_full(recipes: list[h2r.Recipe], file_extension: FileExtension) -> str:
    name = "recipes"
    file = gen_full_path(name, file_extension)

    if not file.stat().st_size > 0:
        recipe_writer = TestRecipeWriter(file, file_extension == FileExtension.md)
        logger.info("Generating %s", file)
        with suppress_logging():
            recipe_writer.write(recipes)
    return file.read_text()


FULL_MD: Final[str] = gen_formatted_full(RECIPE_LIST, FileExtension.md)
FULL_TXT: Final[str] = gen_formatted_full(RECIPE_LIST, FileExtension.txt)
