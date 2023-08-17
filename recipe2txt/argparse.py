# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.
"""
Module for processing commandline-arguments.

Responsible for extracting relevant parameters from the command line arguments, doing basic checking for correctness and
constructing a :py:class:`recipe2txt.fetcher_abstract.AbstractFetcher` from them.
    Attributes:
        logger (logging.Logger): The logger for the module. Receives the constructed logger from
            :py:mod:`recipe2txt.utils.ContextLogger`
        ARGNAMES (Final[list[LiteralString]]): The names of all CLI-flags :py:data:`parser` is configured to check.
        parser (argparse.ArgumentParser): The argument parser used by this program

"""
import argparse
import logging
import os
import sys
from typing import Final, Tuple
from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.fetcher_abstract import Cache
from recipe2txt.file_setup import get_files, erase_files, set_default_output, file_setup, PROGRAM_NAME
from recipe2txt.utils.ContextLogger import get_logger, root_log_setup, string2level
from recipe2txt.utils.misc import URL, read_files, extract_urls, Counts, File

try:
    from recipe2txt.fetcher_async import AsyncFetcher as Fetcher
except ImportError:
    from recipe2txt.fetcher_serial import SerialFetcher as Fetcher  # type: ignore

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from :py:mod:`recipe2txt.utils.ContextLogger`"""


def arg2str(name: str, args: argparse.Namespace) -> str:
    """
    Creates a string representation of a CLI-flag-argument pair.

    Extracts the argument described by :py:obj:`name` from :py:obj:`args` and either returns a string representation of
    the name and the argument or name and 'NOT FOUND' if the argument is not set.
    Args:
        name (): The argparse-attribute name
        args (): The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`

    Returns:
        A string of the format '--name: argument'

    """
    return f"--{name.replace('_', '-')}: {getattr(args, name, 'NOT FOUND')}"


ARGNAMES: Final[list[LiteralString]] = [
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
"""The names of all CLI-flags :py:data:`parser` is configured to check."""


def args2strs(a: argparse.Namespace) -> list[str]:
    """
    Converts all possible CLI-flags :py:mod:`argparse will check for and their values for this run to a list of strings.

    Args:
        a (): The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`

    Returns:
        A list of all 'stringified' flags and their values

    """
    return [arg2str(name, a) for name in ARGNAMES]


parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME,
    description="Scrapes URLs of recipes into text files",
    epilog="[NI] = 'Not implemented (yet)'"
)
"""The argument parser used by this program."""

parser.add_argument("-u", "--url", nargs='+', default=[],
                    help="URLs whose recipes should be added to the recipe-file")
parser.add_argument("-f", "--file", nargs='+', default=[],
                    help="Text-files containing URLs (one per line) whose recipes should be added to the recipe-file")
parser.add_argument("-o", "--output", default="",
                    help="Specifies an output file. If empty or not specified recipes will either be written into"
                         " the current working directory or into the default output file (if set). THIS WILL OVERWRITE"
                         " ANY EXISTING FILE WITH THE SAME NAME.")
parser.add_argument("-v", "--verbosity", default="critical", choices=["debug", "info", "warning", "error", "critical"],
                    help="Sets the 'chattiness' of the program (default 'critical')")
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
                           " 'tests/testfiles/default_output_location.txt').")


def mutex_args_check(a: argparse.Namespace) -> None:
    """
    Verifies that only one of the mutual exclusive flags is set.

    Those flags, namely '--show-appdata', '--erase-appdata' and '--default-output-file', do not influence a normal run
    of the program, but help review and configure the default options and data.
    Args:
        a (): The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
    """
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
    """
    Processes the mutual exclusive flags (see :py:func:`mutex_args_check`)

    Args:
        a (): The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
    """
    if not (a.show_appdata or a.erase_appdata or a.default_output_file):
        return
    mutex_args_check(a)
    if a.show_appdata:
        if files := get_files():
            print(os.linesep.join(files))
        else:
            logger.warning("No files found")
    elif a.erase_appdata:
        erase_files()
    elif a.default_output_file:
        if a.default_output_file != "RESET":
            set_default_output(a.default_output_file)
        else:
            set_default_output("RESET")
    sys.exit(os.EX_OK)


def sancheck_args(a: argparse.Namespace, output: File) -> None:
    """
    Responsible for quickly verifying that certain flags contain valid values.

    Args:
        a (): The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
        output (): The output file the recipes will be written to.
    """
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
    ext = output.suffix
    if a.markdown:
        if ext != ".md":
            logger.warning("The application is instructed to output a markdown file, but the filename extension"
                           " indicates otherwise:'%s'", ext)
    else:
        if ext not in ('', '.txt'):
            logger.warning("The application is instructed to output a text file, but the filename extension"
                           " indicates otherwise:'%s'", ext)


def process_params(a: argparse.Namespace) -> Tuple[set[URL], Fetcher]:
    """
    Responsible for  using the CLI-flags to construct a valid :py:class:`recipe2txt.fetcher_abstract.AbstractFetcher`

    Args:
        a (): The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`

    Returns:
        A tuple of:
            A set of all possible urls gathered from the CLI-arguments.
            An :py:class:`recipe2txt.fetcher_abstract.AbstractFetcher`, initialized with the validated parameters
            gathered from :py:mod:`argparse`

    """
    db_file, recipe_file, log_file = file_setup(a.debug, a.output, a.markdown)
    root_log_setup(string2level[a.verbosity], str(log_file))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("CLI-ARGS: %s\t%s", os.linesep, (os.linesep + '\t').join(args2strs(a)))
    logger.info("--- Preparing arguments ---")
    sancheck_args(a, recipe_file)
    if recipe_file.stat().st_size > 0:
        logger.warning("The output-file %s already exists. It will be overwritten.", recipe_file)
    else:
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
