import asyncio
import os.path
import argparse
import sys
from os import linesep
from typing import Final, Tuple
from xdg_base_dirs import xdg_data_home
from shutil import rmtree
from recipe2txt.fetcher import Fetcher, Cache
from recipe2txt.utils.misc import *
from recipe2txt.sql import is_accessible_db, AccessibleDatabase


def process_urls(strings: list[str]) -> set[URL]:
    processed: set[URL] = set()
    for string in strings:
        string = string.replace(linesep, '')
        string.strip()
        if not string: continue
        c = dprint(4, "Processing", string)
        c = while_context(c)
        if not string.startswith("http"):
            string = "http://" + string
        if is_url(string):
            url = string
            url = cutoff(url, "/ref=", "?")
            if url in processed:
                dprint(2, "\t", "Already queued", context=c)
            else:
                processed.add(url)
        else:
            dprint(1, "\t", "Not an URL", context=c)
    return processed


program_name: Final[str] = "recipes2txt"
default_data_directory: Final[str] = os.path.join(xdg_data_home(), program_name)
debug_data_directory: Final[str] = os.path.join(os.path.dirname(__file__), "test", "testfiles", "data")

db_name: Final[str] = program_name + ".sqlite3"
recipes_name_txt: Final[str] = "recipes.txt"
recipes_name_md: Final[str] = "recipes.md"
default_urls_name: Final[str] = "urls.txt"
default_output_location_name: Final[str] = "default_output_location.txt"


def file_setup(debug: bool = False, output: str = "", markdown: bool = False) -> Tuple[AccessibleDatabase, File]:
    global default_data_directory
    global debug_data_directory

    if debug:
        db_path = debug_data_directory
    else:
        db_path = default_data_directory
    if not ensure_existence_dir(db_path):
        print("Data directory cannot be created", file=sys.stderr)
        exit(os.EX_IOERR)
    db_path = os.path.join(db_path, db_name)
    if is_accessible_db(db_path):
        db_file = db_path
    else:
        print("Database not accessible:", db_path, file=sys.stderr)
        exit(os.EX_IOERR)

    if output:
        base, filename = os.path.split(output)
        output = ensure_accessible_file_critical(filename, base)
    else:
        if debug:
            output_location_file = os.path.join(debug_data_directory, default_output_location_name)
        else:
            output_location_file = os.path.join(default_data_directory, default_output_location_name)
        if os.path.isfile(output_location_file):
            with open(output_location_file, 'r') as file:
                output = file.readline().rstrip(linesep)
                if markdown:
                    output = file.readline().rstrip(linesep)
            base, filename = os.path.split(output)
            output = ensure_accessible_file_critical(filename, base)
        else:
            if markdown:
                recipes_name = recipes_name_md
            else:
                recipes_name = recipes_name_txt
            output = ensure_accessible_file_critical(recipes_name, os.getcwd())
    dprint(4, "Output set to:", output)

    return db_file, output


_parser = argparse.ArgumentParser(
    prog=program_name,
    description="Scrapes URLs of recipes into text files",
    epilog="[NI] = 'Not implemented (yet)'"
)

_parser.add_argument("-u", "--url", nargs='+', default=[],
                     help="URLs whose recipes should be added to the recipe-file")
_parser.add_argument("-f", "--file", nargs='+', default=[],
                     help="Text-files containing URLs (one per line) whose recipes should be added to the recipe-file")
_parser.add_argument("-o", "--output", default="",
                     help="Specifies an output file. If empty or not specified recipes will either be written into"
                          "the current working directory or into the default output file (if set).")
_parser.add_argument("-v", "--verbosity", type=int, default=2, choices=range(0, 5),
                     help="Sets the 'chattiness' of the program (low = 1, high = 4, quiet = 0")
_parser.add_argument("-con", "--connections", type=int, default=4,
                     help="Sets the number of simultaneous connections")
_parser.add_argument("-ia", "--ignore-added", action="store_true",
                     help="[NI]Writes recipe to file regardless if it has already been added")
_parser.add_argument("-c", "--cache", choices=["only", "new", "default"], default="default",
                     help="Controls how the program should handle its cache: With 'only' no new data will be downloaded"
                     ", the recipes will be generated from data that has been downloaded previously. If a recipe is not"
                          " in the cache, it will not be written into the final output. 'new' will make the program"
                          " ignore any saved data and download the requested recipes even if they have already been"
                          " downloaded. Old data will be replaced by the new version, if it is available."
                          " The 'default' will fetch and merge missing data with the data already saved, only inserting"
                          " new data into the cache where there was none previously.")
_parser.add_argument("-d", "--debug", action="store_true",
                     help="Activates debug-mode: Changes the directory for application data")
_parser.add_argument("-t", "--timeout", type=float, default=5.0,
                     help="Sets the number of seconds the program waits for an individual website to respond" +
                          "(eg. sets the connect-value of aiohttp.ClientTimeout)")
_parser.add_argument("-md", "--markdown", action="store_true",
                     help="Generates markdown-output instead of .txt")

settings = _parser.add_mutually_exclusive_group()
settings.add_argument("-sa", "--show-appdata", action="store_true",
                      help="Shows data- and cache-files used by this program")
settings.add_argument("-erase", "--erase-appdata", action="store_true",
                      help="Erases all data- and cache-files used by this program")
settings.add_argument("-do", "--default-output-file", default="",
                      help="Sets a file where recipes should be written to if no " +
                           "output-file is explicitly passed via '-o' or '--output'." +
                           "Pass 'RESET' to reset the default output to the current working directory." +
                           " Does not work in debug mode (default-output-file is automatically set by"
                           " 'tests/testfiles/data/default_output_location.txt').")


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
    "cache",
    "debug",
    "timeout",
    "markdown",
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
            if len(sys.argv) > 3:
                flag_name = "--default-output-file"

        if flag_name:
            _parse_error(flag_name + " cannot be used with any other flags")


def show_files() -> None:
    global default_data_directory
    global debug_data_directory

    files = []
    if os.path.isdir(default_data_directory):
        files = [os.path.join(default_data_directory, file) for file in os.listdir(default_data_directory)]

    files_debug = []
    if os.path.isdir(debug_data_directory):
        files_debug = [os.path.join(debug_data_directory, file) for file in os.listdir(debug_data_directory)]

    files += files_debug
    if files:
        print(*files, sep=linesep)
    else:
        print("No files found")


def erase_files() -> None:
    global default_data_directory
    if os.path.isdir(default_data_directory):
        print("Deleting:", default_data_directory)
        rmtree(default_data_directory)

    global debug_data_directory
    if os.path.isdir(debug_data_directory):
        print("Deleting:", debug_data_directory)
        rmtree(debug_data_directory)


def set_default_output(filepath: str) -> None:
    if filepath == "RESET":
        try:
            os.remove(os.path.join(default_data_directory, default_output_location_name))
            print("Removed default output location. When called without specifying the output-file recipes will"
                  " now be written in the current working directory with the name", recipes_name_txt)
        except FileNotFoundError:
            print("No default output set")
            pass
        except OSError as e:
            print("Error while deleting file {}: {}"
                  .format(full_path(full_path(filepath)), getattr(e, 'message', repr(e))),
                  file=sys.stderr)
            exit(os.EX_IOERR)
    else:
        base, name = os.path.split(filepath)
        filepath = ensure_accessible_file_critical(name, base)

        try:
            ensure_existence_dir(default_data_directory)
            with open(os.path.join(default_data_directory, default_output_location_name), 'a') as file:
                file.write(filepath)
                file.write(linesep)
            print("Set default output location to", filepath)
        except OSError as e:
            print("Error while creating or accessing file {}: {}"
                  .format(filepath, getattr(e, 'message', repr(e))),
                  file=sys.stderr)
            exit(os.EX_IOERR)


def mutex_args(a: argparse.Namespace) -> None:
    if not (a.show_appdata or a.erase_appdata or a.default_output_file):
        return
    mutex_args_check(a)
    if a.show_appdata:
        show_files()
    elif a.erase_appdata:
        erase_files()
    elif a.default_output_file:
        set_default_output(a.default_output_file)
    exit(os.EX_OK)


def sancheck_args(a: argparse.Namespace) -> None:
    if not (a.file or a.url):
        _parse_error("Nothing to process: No file or url passed")
    if a.connections < 1:
        dprint(3, "Number of connections smaller than 1, setting to 1 ")
        a.connections = 1
    if a.timeout <= 0.0:
        dprint(3, "Network timeout equal to or smaller than 0, setting to 0.1")
        a.timeout = 0.1


def process_params(a: argparse.Namespace) -> Tuple[set[URL], Fetcher]:
    sancheck_args(a)
    db_file, recipe_file = file_setup(a.debug, a.output, a.markdown)
    mark_stage("Preparing arguments")
    unprocessed: list[str] = read_files(*a.file)
    unprocessed += a.url
    processed: set[URL] = process_urls(unprocessed)
    if not len(processed):
        dprint(1, "No valid URL passed")
        exit(os.EX_DATAERR)
    counts = Counts()
    counts.strings = len(unprocessed)

    f = Fetcher(output=recipe_file, connections=a.connections,
                counts=counts, database=db_file,
                timeout=a.timeout, markdown=a.markdown,
                cache=Cache(a.cache))

    return processed, f


if __name__ == '__main__':
    a = _parser.parse_args()
    set_vlevel(a.verbosity)

    dprint(4, "CLI-ARGS:", *args2strs(a), sep=linesep + "\t")
    mutex_args(a)
    urls, fetcher = process_params(a)
    asyncio.run(fetcher.fetch(urls))
    mark_stage("Summary")
    dprint(3, str(fetcher.get_counts()))
    exit(os.EX_OK)
