import logging
import sys
import urllib.request
import os
from typing import Final

import recipe2txt.html2recipe as h2r
from recipe2txt.fetcher_abstract import AbstractFetcher, Cache
from recipe2txt.utils.misc import URL, is_url, File, ensure_accessible_file_critical
from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM, root_log_setup, suppress_logging
from recipe2txt.sql import is_accessible_db, AccessibleDatabase
import recipe_scrapers
from recipe2txt.utils.conditional_imports import LiteralString

__all__ = ["html", "html_bad", "recipe_list", "md_list", "txt_list", "url_list", "full_txt", "full_md"]

if __name__ == '__main__':
    root_log_setup(logging.DEBUG)

logger = get_logger(__name__)
root = os.path.dirname(__file__)


def get_urls() -> list[URL]:
    with open(os.path.join(root, "URLs"), "r") as file:
        urls = [line.rstrip(os.linesep) for line in file.readlines() if is_url(line)]
    urls.sort()
    return urls  # type: ignore


url_list: Final[list[URL]] = get_urls()


class FileExtension(StrEnum):
    txt = ".txt"
    md = ".md"
    parsed = ".parsed"
    html = ".html"


def gen_full_path(filename: str, file_extension: FileExtension) -> File:
    f_e = f"{file_extension}"
    return ensure_accessible_file_critical(filename + f_e, root, f_e[1:])


filenames: Final[list[str]] = [url.rsplit(":", 1)[1] for url in url_list if is_url(url)]
filenames.sort()


def fetch_url(url: URL, filename: str) -> bytes:
    if not os.path.getsize(filename) > 0:
        logger.info("Generating %s from %s", filename, url)
        html = urllib.request.get(url).content
        with open(filename, "wb") as file:
            file.write(html)
    else:
        logger.info("Already available: %s", filename)
        with open(filename, "rb") as file:
            html = file.read()
    return html


def gen_html(filenames: list[str]) -> list[bytes]:
    html_paths = [gen_full_path(name, FileExtension.html) for name in filenames]
    html = []

    for url, filename in zip(url_list, html_paths):
        html.append(fetch_url(url, filename))
    return html


delim = "---"


def parse_html(filename: str, filename_parsed: str, url: URL) -> h2r.Recipe:
    with open(filename, "rb") as file:
        html = file.read()
        r = recipe_scrapers.scrape_html(html=html, org_url=url)  # type: ignore
        attributes = []
        with QCM(logger, logger.info, "Scraping %s", url):
            for method in h2r.METHODS:
                try:
                    a = getattr(r, method)()
                    attributes.append(a)
                except Exception:
                    logger.error("%s not found", method)
                    attributes.append(h2r.NA)
            attributes += [url, int(h2r.gen_status(attributes)), h2r.SCRAPER_VERSION]
            recipe = h2r.Recipe(*attributes)
    with open(filename_parsed, "w") as file:
        for a in attributes:
            if isinstance(a, list):
                a = os.linesep.join(a)
            file.write(str(a))
            file.write(os.linesep + delim + os.linesep)
    return recipe


def parse_txt(path: str) -> h2r.Recipe:
    attributes = []
    tmp = []
    with open(path, "r") as file:
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
    recipe = h2r.Recipe(*t)  # type: ignore
    return recipe


def gen_parsed(filenames: list[str]) -> list[h2r.Recipe]:
    files_html = [gen_full_path(name, FileExtension.html) for name in filenames]
    files_parsed = [gen_full_path(name, FileExtension.parsed) for name in filenames]
    recipes = []

    for html, parsed, url in zip(files_html, files_parsed, url_list):
        if not os.path.getsize(parsed) > 0:
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
        if not os.path.getsize(formatted_file) > 0:
            logger.info("Generating %s from %s", formatted_file, parsed)
            recipe = parse_txt(parsed)
            if file_extension is FileExtension.md:
                tmp_list = h2r._re2md(recipe)
            else:
                tmp_list = h2r._re2txt(recipe)
            with open(formatted_file, "w") as f:
                f.writelines(tmp_list)
            formatted = "".join(tmp_list)
            formatted_recipes.append(formatted)
        else:
            logger.info("Already available: %s",  formatted_file)
            with open(formatted_file, "r") as f:
                formatted_recipes.append("".join(f.readlines()))
    return formatted_recipes


html_list: Final[list[bytes]] = gen_html(filenames)
_bad_url: Final[str] = "https://creativecommons.org/licenses/by/4.0/"
html_bad: Final[tuple[str, bytes]] = (_bad_url, fetch_url(URL(_bad_url),
                                                          gen_full_path("FAIL_cc_4_0", FileExtension.html)))
recipe_list: Final[list[h2r.Recipe]] = gen_parsed(filenames)
md_list: Final[list[str]] = gen_formatted(filenames, FileExtension.md)
txt_list: Final[list[str]] = gen_formatted(filenames, FileExtension.txt)

db: AccessibleDatabase
_db = os.path.join(root, "testfile_db.sqlite3")
if is_accessible_db(_db):
    db = _db
else:
    sys.exit(f"Database not accessible: {_db}")

url2html: dict[str, bytes] = {url: html for url, html in zip(url_list, html_list)}


class TestFileFetcher(AbstractFetcher):

    def fetch(self, urls: set[URL]):
        urls = super().require_fetching(urls)
        for url in urls:
            html = url2html[url]
            self.html2db(url, html)  # type: ignore
            # TODO
        lines = self.gen_lines()
        self.write(lines)


def gen_formatted_full(urls: set[URL], file_extension: FileExtension) -> list[str]:
    name = "recipes"
    file = gen_full_path(name, file_extension)
    file_exists = os.path.getsize(file) > 0

    if not file_exists:
        f = TestFileFetcher(output=file, database=db, cache=Cache.new)
        f.markdown = file_extension is FileExtension.md
        logger.info("Generating %s", file)
        with suppress_logging():
            f.fetch(urls)
    with open(file, "r") as to_read:
        lines = to_read.readlines()

    return lines


url_set = set(url_list)
full_md: Final[list[str]] = gen_formatted_full(url_set, FileExtension.md)
full_txt: Final[list[str]] = gen_formatted_full(url_set, FileExtension.txt)
