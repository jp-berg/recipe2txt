import asyncio
import os.path
import argparse
import sys
from os import linesep
from typing import Final, Tuple
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


def file_setup(debug: bool = False, output: str = "") -> Tuple[File, File]:
    workdir: str = os.getcwd()
    default_data_directory: str = os.path.join(xdg_data_home(), program_name)
    if debug:
        workdir = os.path.join(os.path.dirname(__file__), "tests", "testfiles")
        default_data_directory = os.path.join(workdir, "data")

    known_urls_file = ensure_accessible_file_critical(known_urls_name, default_data_directory)
    dprint(4, "Urls read from:", known_urls_file)
    if output:
        base, filename = os.path.split(output)
        output = ensure_accessible_file_critical(filename, base)
    else:
        output = ensure_accessible_file_critical(recipes_name, workdir)

    dprint(4, "Output set to:", output)
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


def mutex_args_check(a: argparse.Namespace) -> None:
    if len(sys.argv) > 2:

        flag_name: str = ""
        if a.show_appdata:
            flag_name = "--show-appdata"
        elif a.erase_appdata:
            flag_name = "--erase-appdata"
        elif a.default_output_file:
            flag_name = "--default-output-file"

        if flag_name:
            _parse_error(flag_name + " cannot be used with any other flags")


def show_files() -> str:
    print("[STUB]: show_files()")
    return ""


def erase_files() -> None:
    print("[STUB]: erase_files()")
    pass


def set_recipe_file() -> None:
    print("[STUB]: set_recipe_file()")
    pass


def mutex_args(a: argparse.Namespace) -> None:
    if not (a.show_appdata or a.erase_appdata or a.default_output_file):
        return
    mutex_args_check(a)
    if a.show_appdata:
        show_files()
    elif a.erase_appdata:
        erase_files()
    elif a.default_output_file:
        set_recipe_file()
    exit(os.EX_OK)


def sancheck_args(a: argparse.Namespace) -> None:
    if not (a.file or a.url):
        _parse_error("Nothing to process: No file or url passed")
    if a.connections < 1:
        dprint(3, "Number of connections smaller than 1, setting to 1 ")
        a.connections = 1
    if a.servings < 1:
        if a.servings != -123456789:
            dprint(3, "Number of servings smaller than 1, setting to 1")
            a.servings = 1


def process_params(a: argparse.Namespace) -> Tuple[set[URL], Fetcher]:
    sancheck_args(a)
    known_urls_file, recipe_file = file_setup(a.debug, a.output)
    known_urls: set[URL]
    if a.ignore_added:
        known_urls = []
    else:
        known_urls: set[URL] = set([line for line in read_files(known_urls_file) if is_url(line)])
    unprocessed: list[str] = read_files(*a.file)
    unprocessed += a.url
    processed: set[URL] = process_urls(known_urls, unprocessed)
    if not len(processed):
        dprint(1, "No valid URL passed")
        exit(os.EX_DATAERR)
    counts = Counts()
    counts.strings = len(unprocessed)

    f = Fetcher(output=recipe_file, connections=a.connections,
                counts=counts, known_urls_file=known_urls_file)

    return processed, f


if __name__ == '__main__':
    a = _parser.parse_args()
    set_vlevel(a.verbosity)

    dprint(4, "CLI-ARGS:", *args2strs(a), sep="\n\t")
    mutex_args(a)
    urls, fetcher = process_params(a)
    asyncio.run(fetcher.fetch(urls))

    dprint(3, str(fetcher.get_counts()))
    exit(os.EX_OK)
