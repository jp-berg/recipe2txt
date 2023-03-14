import asyncio
import os.path
import argparse
import sys
from os import linesep, getcwd
from sys import argv
from typing import NamedTuple

from xdg_base_dirs import xdg_data_home
from recipe2txt.fetcher import Fetcher
from recipe2txt.utils.misc import *


def process_urls(known_urls: set[URL], strings: list[str]) -> set[URL]:
    processed: set[URL] = set()
    for string in strings:
        c = while_context(dprint(3, "Processing'", string, "'"))
        string = string.replace(linesep, '')
        string.strip()
        if not string.startswith("http"):
            string = "http://" + string
        if is_url(string):
            url = string
            url = cutoff(url, "/ref=", "?")
            if url in known_urls:
                dprint(2, "Already scraped", context=c)
                continue
            if url in processed:
                dprint(2, "Already queued", context=c)
            else:
                processed.add(url)
        else:
            dprint(1, "Not an URL", context=c)
    return processed


program_name: Final[str] = "recipes2txt"

known_urls_name: Final[str] = "knownURLs.txt"
recipes_name: Final[str] = "recipes.txt"
default_urls_name: Final[str] = "urls.txt"


def file_setup(debug: bool = False, output: str = "") -> Tuple[str, str]:
    workdir: str = os.getcwd()
    default_data_directory: str = os.path.join(xdg_data_home(), program_name)
    if debug:
        workdir = os.path.join(os.path.dirname(__file__), "tests", "testfiles")
        default_data_directory = os.path.join(workdir, "data")

    known_urls_file = ensure_existence_file_critical(known_urls_name, default_data_directory)
    if output:
        output = ensure_existence_file_critical(output)
    else:
        output = ensure_existence_file_critical(recipes_name, workdir)

    return known_urls_file, output


_parser = argparse.ArgumentParser(
    prog=program_name,
    description="Scrapes URLs of recipes into text files",
    epilog="[NI] = 'Not implemented (yet)'"
)

_parser.add_argument("-u", "--url", nargs='+', default=[],
                     help="[NI]List URLs whose recipes should be added to the recipe-file")
_parser.add_argument("-f", "--file", nargs='+', default=[],
                     help="[NI]List text-files containing URLs whose recipes should be added to the recipe-file")
_parser.add_argument("-o", "--output", default="",
                     help="[NI]Specifies an output file")
_parser.add_argument("-v", "--verbosity", type=int, default=2, choices=range(0, 5),
                     help="[NI]Sets the 'chattiness' of the program (low = 1, high = 4, quiet = 0")
_parser.add_argument("-c", "--connections", type=int, default=4,
                     help="[NI]Sets the number of simultaneous connections")
_parser.add_argument("-ia", "--ignore-added", action="store_true",
                     help="[NI]Writes recipe to file regardless if it has already been added")
_parser.add_argument("-ic", "--ignore-cached", action="store_true",
                     help="[NI]Downloads the requested recipes even if they have already been downloaded")
_parser.add_argument("-hm", "--hours_minutes", action="store_true",
                     help="[NI]Stores durations as hrs:min instead of min")
_parser.add_argument("-se", "--servings", type=int, default=-123456789, #magic number
                     help="[NI]Sets to how many servings the ingredient list should be converted" +
                          " (if the number of servings is specified)")
_parser.add_argument("-d", "--debug", action="store_true",
                     help="[NI]Activates debug-mode: Changes the directory for application data")

settings = _parser.add_mutually_exclusive_group()
settings.add_argument("-sa", "--show-appdata", action="store_true",
                      help="[NI]Shows data- and cache-files used by this program")
settings.add_argument("-e", "--erase-appdata", action="store_true",
                      help="[NI]Erases all data- and cache-files used by this program")
settings.add_argument("-do", "--default-output-file",
                      help="[NI]Sets a file where recipes should be written to if no " +
                           "output-file is explicitly passed via '-o' or '--output'")


def _parse_error(msg: str) -> None:
    _parser.error(msg)


def arg2str(name: str, obj: object) -> str:
    attr = name
    name = "--" + name.replace("_", "-")
    out: str = name + ": "
    try:
        val = getattr(obj, attr)
        out += str(val)
    except AttributeError:
        out += "NOT FOUND"
    return out


_argnames: list[str] = [
    "url",
    "file",
    "output",
    "verbosity",
    "connections",
    "ignore_added",
    "ignore_cached",
    "hours_minutes",
    "servings",
    "debug",
    "show_files",
    "erase_appdata",
    "standard_output_file"
]


def args2strs(a: argparse.Namespace) -> list[str]:
    return [arg2str(name, a) for name in _argnames]


def cli_mutex(a: argparse.Namespace) -> None:
    if len(sys.argv) > 2:
        flag_name: str = ""
        if a.show_files:
            flag_name = "--show-files"
        elif a.delete:
            flag_name = "--delete"
        elif a.standard_output_file:
            flag_name = "--standard-output-file"

        if flag_name:
            print(flag_name, "cannot be used with other flags", file=sys.stderr)
            exit(1)


if __name__ == '__main__':
    a = _parser.parse_args()
    set_vlevel(a.verbosity)

    dprint(4, "CLI-ARGS:", *args2strs(a), sep="\n\t")
    exit(os.EX_OK)

    known_urls: set[URL] = set()
    if os.path.isfile(known_urls_file):
        with open(known_urls_file, 'r') as file:
            known_urls = set([url for url in file.readlines() if is_url(url)])

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
