import argparse
import logging
import os
import sys
from typing import Final, Tuple
from recipe2txt.utils.conditional_imports import LiteralString, Fetcher
from recipe2txt.fetcher_abstract import Cache
from recipe2txt.file_setup import show_files, erase_files, set_default_output, file_setup, PROGRAM_NAME
from recipe2txt.utils.ContextLogger import get_logger, root_log_setup, string2level
from recipe2txt.utils.misc import URL, read_files, extract_urls, Counts, ensure_accessible_file_critical

logger = get_logger(__name__)


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


parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME,
    description="Scrapes URLs of recipes into text files",
    epilog="[NI] = 'Not implemented (yet)'"
)

parser.add_argument("-u", "--url", nargs='+', default=[],
                    help="URLs whose recipes should be added to the recipe-file")
parser.add_argument("-f", "--file", nargs='+', default=[],
                    help="Text-files containing URLs (one per line) whose recipes should be added to the recipe-file")
parser.add_argument("-o", "--output", default="",
                    help="Specifies an output file. If empty or not specified recipes will either be written into"
                         "the current working directory or into the default output file (if set).")
parser.add_argument("-v", "--verbosity", default="critical", choices=["debug", "info", "warning", "error", "critical"],
                    help="Sets the 'chattiness' of the program (default 'critical'")
parser.add_argument("-con", "--connections", type=int, default=4 if Fetcher.is_async else 1,
                    help="Sets the number of simultaneous connections (default 4). If package 'aiohttp' is not "
                         "installed the number of simultaneous connections will always be 1.")
parser.add_argument("-ia", "--ignore-added", action="store_true",
                    help="[NI]Writes recipe to file regardless if it has already been added")
parser.add_argument("-c", "--cache", choices=["only", "new", "default"], default="default",
                    help="Controls how the program should handle its cache: With 'only' no new data will be downloaded"
                         ", the recipes will be generated from data that has been downloaded previously. If a recipe"
                         " is not in the cache, it will not be written into the final output. 'new' will make the"
                         " program ignore any saved data and download the requested recipes even if they have already"
                         " been downloaded. Old data will be replaced by the new version, if it is available."
                         " The 'default' will fetch and merge missing data with the data already saved, only inserting"
                         " new data into the cache where there was none previously.")
parser.add_argument("-d", "--debug", action="store_true",
                    help="Activates debug-mode: Changes the directory for application data")
parser.add_argument("-t", "--timeout", type=float, default=5.0,
                    help="Sets the number of seconds the program waits for an individual website to respond" +
                         "(eg. sets the connect-value of aiohttp.ClientTimeout)")
parser.add_argument("-md", "--markdown", action="store_true",
                    help="Generates markdown-output instead of .txt")

settings = parser.add_mutually_exclusive_group()
settings.add_argument("-sa", "--show-appdata", action="store_true",
                      help="Shows data- and cache-files used by this program")
settings.add_argument("-erase", "--erase-appdata", action="store_true",
                      help="Erases all data- and cache-files used by this program")
settings.add_argument("-do", "--default-output-file", default="",
                      help="Sets a file where recipes should be written to if no" +
                           " output-file is explicitly passed via '-o' or '--output'." +
                           " Pass 'RESET' to reset the default output to the current working directory." +
                           " Does not work in debug mode (default-output-file is automatically set by"
                           " 'tests/testfiles/data/default_output_location.txt').")


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
            parser.error(flag_name + " cannot be used with any other flags")


def mutex_args(a: argparse.Namespace) -> None:
    if not (a.show_appdata or a.erase_appdata or a.default_output_file):
        return
    mutex_args_check(a)
    if a.show_appdata:
        show_files()
    elif a.erase_appdata:
        erase_files()
    elif a.default_output_file:
        if a.default_output_file != "RESET":
            file = ensure_accessible_file_critical(a.default_output_file)
            set_default_output(a.default_output_file)
        else:
            set_default_output("RESET")
    sys.exit(os.EX_OK)


def sancheck_args(a: argparse.Namespace, output: str) -> None:
    if not (a.file or a.url):
        parser.error("Nothing to process: No file or url passed")
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
        logger.debug("CLI-ARGS: %s\t%s", os.linesep, (os.linesep + '\t').join(args2strs(a)))
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
