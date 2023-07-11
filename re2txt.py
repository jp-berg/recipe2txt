import logging
import os.path
import argparse
import sys
from os import linesep
from typing import Final, Tuple, Literal
from time import gmtime, strftime

from recipe2txt.html2recipe import errors2str

from shutil import rmtree
from xdg_base_dirs import xdg_data_home
from recipe2txt.utils.ContextLogger import get_logger, root_log_setup, string2level
from recipe2txt.utils.misc import *
from recipe2txt.sql import AccessibleDatabase, ensure_accessible_db_critical
from recipe2txt.fetcher_abstract import Cache
from recipe2txt.utils.conditional_imports import LiteralString, Fetcher

logger = get_logger(__name__)

PROGRAM_NAME: Final[LiteralString] = "recipes2txt"
DEFAULT_DATA_DIRECTORY: Final[str] = os.path.join(xdg_data_home(), PROGRAM_NAME)
DEBUG_DATA_DIRECTORY: Final[str] = os.path.join(os.path.dirname(__file__), "test", "testfiles", "data")

LOG_NAME: Final[LiteralString] = "debug.log"
DB_NAME: Final[LiteralString] = PROGRAM_NAME + ".sqlite3"
RECIPES_NAME: Final[LiteralString] = "recipes"
RECIPES_NAME_TXT: Final[LiteralString] = RECIPES_NAME + ".txt"
RECIPES_NAME_MD: Final[LiteralString] = RECIPES_NAME + ".md"
DEFAULT_URLS_NAME: Final[LiteralString] = "urls.txt"
DEFAULT_OUTPUT_LOCATION_NAME: Final[LiteralString] = "default_output_location.txt"


def get_data_directory(debug: bool = False) -> Directory:
    tmp = DEBUG_DATA_DIRECTORY if debug else DEFAULT_DATA_DIRECTORY
    if not (data_path := ensure_existence_dir(tmp)):
        print("Data directory cannot be created: ", tmp, file=sys.stderr)
        sys.exit(os.EX_IOERR)
    return data_path


def file_setup(debug: bool = False, output: str = "", markdown: bool = False) -> Tuple[AccessibleDatabase, File, File]:
    data_path = get_data_directory(debug)
    log_file = ensure_accessible_file_critical(LOG_NAME, data_path)
    db_file = ensure_accessible_db_critical(DB_NAME, data_path)

    if output:
        output = ensure_accessible_file_critical(output)
    else:
        if debug:
            output_location_file = os.path.join(DEBUG_DATA_DIRECTORY, DEFAULT_OUTPUT_LOCATION_NAME)
        else:
            output_location_file = os.path.join(DEFAULT_DATA_DIRECTORY, DEFAULT_OUTPUT_LOCATION_NAME)
        if os.path.isfile(output_location_file):
            with open(output_location_file, 'r') as file:
                output = file.readline().rstrip(linesep)
                if markdown:
                    output = file.readline().rstrip(linesep)
            base, filename = os.path.split(output)
            output = ensure_accessible_file_critical(output)
        else:
            if markdown:
                recipes_name = RECIPES_NAME_MD
            else:
                recipes_name = RECIPES_NAME_TXT
            output = ensure_accessible_file_critical(recipes_name, Directory(os.getcwd()))

    return db_file, output, log_file


how_to_report_txt: Final[LiteralString] = \
    """During its execution the program encountered errors while trying to scrape recipes.
In cases where the error seems to originate from the underlying library 'recipe-scrapers' an error-report per error
has been generated and saved to a file.
You find those files in the folders adjacent to this file. There is one folder per error-encountering excecution of the 
program (naming format: 'Year-Month-Day_Hour-Minute-Second' when finishing execution). 
If you want those errors fixed, go to 'https://github.com/hhursev/recipe-scrapers/issues' and search for each
filename (without the '.md'-extension). If you cannot find a matching report for a filename, please click 'New Issue'
and select 'Scraper Bug Report'. Paste the filename (without the '.md'-extension) into the 'Title'-Field and the
contents of the file into the 'Write'-field. Check the 'Pre-filling  checks'-boxes ONLY if you made sure to follow
their instructions. After that click 'Submit new issue'. The maintainers of the library will have a look at your
problem and try to fix it. Please note that they are volunteers and under no obligation to help you. Be kind to them.
"""


def write_errors(debug: bool = False) -> int:
    if not (errors := errors2str()):
        return 0

    logger.info("---Writing error reports---")

    data_path = get_data_directory(debug)
    if not (error_dir := ensure_existence_dir(data_path, "error_reports")):
        logger.error("Could not create %s, no reports will be written", os.path.join(data_path, "error_reports"))
        return 0
    how_to_report_file = os.path.join(error_dir, "how_to_report_errors.txt")
    if not os.path.isfile(how_to_report_file):
        with open(how_to_report_file, "w") as f:
            f.write(how_to_report_txt)

    current_time = strftime("%Y-%m-%d_%H-%M-%S", gmtime())
    current_error_dir = os.path.join(error_dir, current_time)

    i = 1
    tmp = current_error_dir
    while os.path.isdir(tmp):
        tmp = f"{current_error_dir}-{i}"
        i += 1
    current_error_dir = tmp
    os.mkdir(current_error_dir)

    for title, msg in errors:
        filename = os.path.join(current_error_dir, title + ".md")
        with open(filename, "w") as f:
            f.write(msg)

    warn_msg = f"During its execution the program encountered recipes " \
               f"that could not be (completely) scraped.{linesep}" \
               f" Please see {linesep}%s{linesep}if you want to help fix this."
    logger.warning(warn_msg, how_to_report_file)

    return len(errors)


_parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME,
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
_parser.add_argument("-v", "--verbosity", default="critical", choices=["debug", "info", "warning", "error", "critical"],
                     help="Sets the 'chattiness' of the program (default 'critical'")
_parser.add_argument("-con", "--connections", type=int, default=4 if Fetcher.is_async else 1,
                     help="Sets the number of simultaneous connections (default 4). If package 'aiohttp' is not "
                          "installed the number of simultaneous connections will always be 1.")
_parser.add_argument("-ia", "--ignore-added", action="store_true",
                     help="[NI]Writes recipe to file regardless if it has already been added")
_parser.add_argument("-c", "--cache", choices=["only", "new", "default"], default="default",
                     help="Controls how the program should handle its cache: With 'only' no new data will be downloaded"
                          ", the recipes will be generated from data that has been downloaded previously. If a recipe"
                          " is not in the cache, it will not be written into the final output. 'new' will make the"
                          " program ignore any saved data and download the requested recipes even if they have already"
                          " been downloaded. Old data will be replaced by the new version, if it is available."
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


_ARGNAMES: Final[list[LiteralString]] = [
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
    return [arg2str(name, a) for name in _ARGNAMES]


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
    files = []
    if os.path.isdir(DEFAULT_DATA_DIRECTORY):
        files = [os.path.join(DEFAULT_DATA_DIRECTORY, file) for file in os.listdir()]

    files_debug = []
    if os.path.isdir(DEBUG_DATA_DIRECTORY):
        files_debug = [os.path.join(DEBUG_DATA_DIRECTORY, file) for file in os.listdir(DEBUG_DATA_DIRECTORY)]

    files += files_debug
    if files:
        print(*files, sep=linesep)
    else:
        print("No files found", file=sys.stderr)


def erase_files() -> None:
    if os.path.isdir(DEFAULT_DATA_DIRECTORY):
        print("Deleting:", DEFAULT_DATA_DIRECTORY)
        rmtree(DEFAULT_DATA_DIRECTORY)

    if os.path.isdir(DEBUG_DATA_DIRECTORY):
        print("Deleting:", DEBUG_DATA_DIRECTORY)
        rmtree(DEBUG_DATA_DIRECTORY)


def set_default_output(filepath: File | Literal["RESET"]) -> None:
    if filepath == "RESET":
        try:
            os.remove(os.path.join(get_data_directory(), DEFAULT_OUTPUT_LOCATION_NAME))
            print("Removed default output location. When called without specifying the output-file recipes will"
                  " now be written in the current working directory with the name", RECIPES_NAME_TXT)
        except FileNotFoundError:
            print("No default output set")
        except OSError as e:
            print("Error while deleting file {}: {}"
                  .format(filepath, getattr(e, 'message', repr(e))),
                  file=sys.stderr)
            sys.exit(os.EX_IOERR)
    else:
        filepath = ensure_accessible_file_critical(DEFAULT_OUTPUT_LOCATION_NAME, get_data_directory())
        with open(filepath, 'a') as file:
            file.write(filepath)
            file.write(os.linesep)
        print("Set default output location to", filepath)


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
    sys.exit(os.EX_OK)


def sancheck_args(a: argparse.Namespace, output: str) -> None:
    if not (a.file or a.url):
        _parse_error("Nothing to process: No file or url passed")
    if a.connections < 1:
        logger.warning("Number of connections smaller than 1, setting to 1 ")
        a.connections = 1
    elif a.connections > 1 and not Fetcher.is_async:
        logger.warning("Number of connections greater than 1, but package aiohttp not installed.")
    if a.timeout <= 0.0:
        logger.warning("Network timeout equal to or smaller than 0, setting to 0.1")
        a.timeout = 0.1
    _dummy, ext = os.path.splitext(output)
    if a.markdown:
        if ext != ".md":
            logger.warning("The application is instructed to output a markdown file, but the filename extension"
                           " indicates otherwise:'%s'", ext)
    else:
        if ext not in ('', '.txt'):
            logger.warning("The application is instructed to output a text file, but the filename extension"
                           " indicates otherwise:'%s'", ext)


def process_params(a: argparse.Namespace) -> Tuple[set[URL], Fetcher]:
    db_file, recipe_file, log_file = file_setup(a.debug, a.output, a.markdown)
    root_log_setup(string2level[a.verbosity], log_file)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("CLI-ARGS: %s\t%s", linesep, (linesep + '\t').join(args2strs(a)))
    logger.info("--- Preparing arguments ---")
    sancheck_args(a, recipe_file)
    logger.info("Output set to: %s", recipe_file)
    unprocessed: list[str] = read_files(*a.file)
    unprocessed += a.url
    processed: set[URL] = extract_urls(unprocessed)
    if not processed:
        logger.critical("No valid URL passed")
        sys.exit(os.EX_DATAERR)
    counts = Counts()
    counts.strings = len(unprocessed)

    f = Fetcher(output=recipe_file, connections=a.connections,
                counts=counts, database=db_file,
                timeout=a.timeout, markdown=a.markdown,
                cache=Cache(a.cache))

    return processed, f


if __name__ == '__main__':
    a = _parser.parse_args()
    mutex_args(a)
    urls, fetcher = process_params(a)
    fetcher.fetch(urls)
    logger.info("--- Summary ---")
    if logger.isEnabledFor(logging.DEBUG):
        logger.info(fetcher.get_counts())
    write_errors(a.debug)
    sys.exit(os.EX_OK)
