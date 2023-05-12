import requests
import os
import recipe2txt.html2recipe as h2r

from typing import Final
from recipe2txt.utils.misc import URL, is_url
from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM
import recipe_scrapers
from sys import version_info

if version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

__all__ = ["html", "html_bad", "recipes", "md", "txt", "urls"]

logger = get_logger(__name__)
root = os.path.dirname(__file__)


def get_urls() -> list[URL]:
    with open(os.path.join(root, "URLs"), "r") as file:
        urls = [line.rstrip(os.linesep) for line in file.readlines() if is_url(line)]
    urls.sort()
    return urls  # type: ignore


urls: Final[list[URL]] = get_urls()


class FileExtension(StrEnum):
    txt = ".txt"
    md = ".md"
    parsed = ".parsed"
    html = ".html"


def gen_full_path(filename: str, file_extension: FileExtension) -> str:
    f_e = f"{file_extension}"
    folder = os.path.join(root, f_e[1:])
    if not os.path.isdir(folder):
        os.mkdir(folder)
    return os.path.join(folder, filename + f_e)


filenames: Final[list[str]] = [url.rsplit(":", 1)[1] for url in urls if is_url(url)]
filenames.sort()


def fetch_url(url: URL, filename: str) -> bytes:
    if not os.path.isfile(filename):
        logger.info(f"Fetching {url}")
        html = requests.get(url).content
        with open(filename, "wb") as file:
            file.write(html)
    else:
        logger.info(f"Already available: {url}")
        with open(filename, "rb") as file:
            html = file.read()
    return html


def gen_html(filenames: list[str]) -> list[bytes]:
    html_paths = [gen_full_path(name, FileExtension.html) for name in filenames]
    html = []

    for url, filename in zip(urls, html_paths):
        html.append(fetch_url(url, filename))
    return html


delim = "---"


def parse_html(filename: str, filename_parsed: str, url: URL) -> h2r.Recipe:
    with open(filename, "rb") as file:
        html = file.read()
        r = recipe_scrapers.scrape_html(html=html, org_url=url)  # type: ignore
        attributes = []
        with QCM(logger, logger.info, f"Scraping {url}"):
            for method in h2r.methods:
                try:
                    a = getattr(r, method)()
                    attributes.append(a)
                except Exception:
                    logger.error(f"{method} not found")
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
    if len(attributes) != len(h2r.recipe_attributes):
        raise ValueError("Error while parsing serialized recipes")
    t = tuple(attributes)
    t = h2r.int2status(t)
    recipe = h2r.Recipe(*t)  # type: ignore
    return recipe


def gen_parsed(filenames: list[str]) -> list[h2r.Recipe]:
    files_html = [gen_full_path(name, FileExtension.html) for name in filenames]
    files_parsed = [gen_full_path(name, FileExtension.parsed) for name in filenames]
    recipes = []

    for html, parsed, url in zip(files_html, files_parsed, urls):
        if not os.path.isfile(parsed):
            logger.info(f"Generating {parsed}")
            recipes.append(parse_html(html, parsed, url))
        else:
            logger.info(f"Already available: {parsed}")
            recipes.append(parse_txt(parsed))
    return recipes


def gen_formatted(filenames: list[str], file_extension: FileExtension) -> list[str]:
    if file_extension not in (FileExtension.md, FileExtension.txt):
        raise ValueError(f"{file_extension} is not a valid extension for this function")
    files_parsed = [gen_full_path(name, FileExtension.parsed) for name in filenames]
    files_formatted = [gen_full_path(name, file_extension) for name in filenames]
    formatted_recipes = []
    for parsed, formatted in zip(files_parsed, files_formatted):
        if not os.path.isfile(formatted):
            logger.info(f"Generating {formatted}")
            recipe = parse_txt(parsed)
            if file_extension is FileExtension.md:
                r = h2r._re2md(recipe)
            else:
                r = h2r._re2txt(recipe)
            with open(formatted, "w") as f:
                f.write(r)
            formatted_recipes.append(r)
        else:
            logger.info(f"Already available: {formatted}")
            with open(formatted, "r") as f:
                formatted_recipes.append("".join(f.readlines()))
    return formatted_recipes


html: Final[list[bytes]] = gen_html(filenames)
_bad_url: Final[str] = "https://creativecommons.org/licenses/by/4.0/"
html_bad: Final[tuple[str, bytes]] = (_bad_url, fetch_url(URL(_bad_url),
                                   gen_full_path("FAIL_cc_4_0", FileExtension.html)))
recipes: Final[list[h2r.Recipe]] = gen_parsed(filenames)
md: Final[list[str]] = gen_formatted(filenames, FileExtension.md)
txt: Final[list[str]] = gen_formatted(filenames, FileExtension.txt)
