# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
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
from recipe2txt.fetcher import Cache, Fetcher
from recipe2txt.utils.conditional_imports import StrEnum
from recipe2txt.utils.ContextLogger import QueueContextManager as QCM
from recipe2txt.utils.ContextLogger import (
    disable_loggers,
    get_logger,
    root_log_setup,
    suppress_logging,
)
from recipe2txt.utils.misc import (
    NEVER_CATCH,
    URL,
    AccessibleDatabase,
    Directory,
    File,
    ensure_accessible_db_critical,
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
                tmp_list = h2r._re2md(recipe)
            else:
                tmp_list = h2r._re2txt(recipe)
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
MD_LIST: Final[list[str]] = gen_formatted(FILENAMES, FileExtension.md)
TXT_LIST: Final[list[str]] = gen_formatted(FILENAMES, FileExtension.txt)

db: AccessibleDatabase = ensure_accessible_db_critical(ROOT, "testfile_db.sqlite3")


class TestFileFetcher(Fetcher):
    URL2HTML: Final[dict[str, bytes]] = {
        url: html for url, html in zip(URL_LIST, HTML_LIST)
    }

    def fetch(self, urls: set[URL]) -> None:
        urls = super().require_fetching(urls)
        for url in urls:
            html = TestFileFetcher.URL2HTML[url]
            self.html2db(url, html)  # type: ignore[arg-type]
            # TODO
        lines = self.gen_lines()
        self.write(lines)


def gen_formatted_full(urls: set[URL], file_extension: FileExtension) -> list[str]:
    name = "recipes"
    file = gen_full_path(name, file_extension)

    if not file.stat().st_size > 0:
        f = TestFileFetcher(output=file, database=db, cache=Cache.NEW)
        f.markdown = file_extension is FileExtension.md
        logger.info("Generating %s", file)
        with suppress_logging():
            f.fetch(urls)
    with open(file, "r") as to_read:
        lines = to_read.readlines()

    return lines


url_set = set(URL_LIST)
FULL_MD: Final[list[str]] = gen_formatted_full(url_set, FileExtension.md)
FULL_TXT: Final[list[str]] = gen_formatted_full(url_set, FileExtension.txt)
