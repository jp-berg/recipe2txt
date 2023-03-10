import asyncio
import os.path
from os import linesep, getcwd
from sys import argv
from xdg_base_dirs import xdg_data_home
from recipe2txt.fetcher import Fetcher
from recipe2txt.utils.misc import *


def process_urls(known_urls: set[URL], strings: list[str]) -> set[URL]:
    processed: set[URL] = set()
    for string in strings:
        string = string.replace(linesep, '')
        string.strip()
        if not string.startswith("http"):
            string = "http://" + string
        if validators.url(string):
            url: URL = URL(string)
            url = cutoff(url, "/ref=", "?")
            if url in known_urls:
                dprint(3, "Already scraped:", url)
                continue
            if url in processed:
                dprint(3, "Already queued:", url)
            else:
                processed.add(url)
        else:
            dprint(3, "Not an URL:", string)
    return processed


program_name: Final[str] = "recipes2txt"

known_urls_name: Final[str] = "knownURLs.txt"
recipes_name: Final[str] = "recipes.txt"
default_urls_name: Final[str] = "urls.txt"

known_urls_file: str
url_file: str
recipe_file: str


def file_setup(debug: bool = False) -> None:
    global known_urls_file
    global url_file
    global recipe_file

    workdir: str = os.path.expanduser(os.path.join("~", "Rezepte"))
    default_data_directory: str = os.path.join(xdg_data_home(), program_name)
    if debug:
        workdir = os.path.join(getcwd(), "tests", "testfiles")
        default_data_directory = os.path.join(workdir, "data")
    known_urls_file = ensure_existence_file(known_urls_name, default_data_directory)
    url_file = ensure_existence_file(default_urls_name, workdir)
    recipe_file = ensure_existence_file(recipes_name, workdir)


if __name__ == '__main__':

    set_vlevel(4)

    args: list[str] = argv[1:]
    args_are_files: bool = True
    debug: bool = True

    file_setup(debug)
    known_urls: set[URL] = set()
    if os.path.isfile(known_urls_file):
        with open(known_urls_file, 'r') as file:
            for url in file.readlines(): known_urls.add(URL(url))

    unprocessed: list[str]
    if args:
        if args_are_files:
            unprocessed = read_files(*args)
        else:
            unprocessed = args
    else:
        unprocessed = read_files(url_file)

    counts = Counts()
    counts.strings = len(unprocessed)
    urls: set[URL] = process_urls(known_urls, unprocessed)
    counts.urls = len(urls)

    f = Fetcher(counts, recipe_file, known_urls_file)
    asyncio.run(f.fetch(urls))

    dprint(3, str(counts))
    exit(0)

