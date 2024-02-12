# Copyright (C) 2024 Jan Philipp Berg <git.7ksst@aleeas.com>
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
"""
Module for processing commandline-arguments.

Responsible for extracting relevant parameters from the command line parameters,
doing basic checking for correctness
and constructing a :py:class:`recipe2txt.fetcher_abstract.AbstractFetcher` from them.
    Attributes:
        logger (logging.Logger): The logger for the module. Receives the constructed
        logger from
            :py:mod:`recipe2txt.utils.ContextLogger`
"""
import argparse
import os
import sys
import textwrap
from functools import cache
from pathlib import Path
from typing import Final, get_args

from recipe2txt.file_setup import (
    CONFIG_FILE,
    JINJA_TEMPLATE_DIR,
    PROGRAM_NAME,
    PYPROJECT,
    erase_files,
    get_db,
    get_default_output,
    get_files,
    get_log,
    get_template_files,
)
from recipe2txt.sql import Database
from recipe2txt.utils.ArgConfig import ArgConfig
from recipe2txt.utils.conditional_imports import tomllib
from recipe2txt.utils.ContextLogger import (
    LOG_LEVEL_NAMES,
    STRING2LEVEL,
    get_logger,
    root_log_setup,
)
from recipe2txt.utils.misc import URL, Counts, File, extract_urls, read_files

try:
    from recipe2txt.fetcher_async import AsyncFetcher as Fetcher
except ImportError:
    from recipe2txt.fetcher import (  # type: ignore[assignment] # isort: skip
        Fetcher as Fetcher,
    )


logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from 
:py:mod:`recipe2txt.utils.ContextLogger`"""


class FileListingArgParse(argparse.ArgumentParser):
    def format_help(self) -> str:
        help_msg = super().format_help()
        files = get_files()
        files.sort()
        files_str = (
            os.linesep + "   " + (os.linesep + "   ").join(files) if files else " none"
        )
        help_msg += (
            os.linesep
            + "files created or used by this program:"
            + files_str
            + os.linesep
        )
        return help_msg


AIOHTTP_NOT_AVAILABLE_MSG: Final = (
    textwrap.dedent(
        """
    Since the package 'aiohttp' is not installed the number of
    simultaneous connections will always be 1. Thus this flag and its
    parameters will not be evaluated. 
    """
    )
    if not Fetcher.is_async
    else ""
)

WHICH_VALUE_SET_MSG: Final = (
    "sets the connect-value of aiohttp.ClientTimeout"
    if Fetcher.is_async
    else "sets the timeout-argument of urllib.request.urlopen"
)


def config_args(config_file: Path) -> argparse.ArgumentParser:
    """
    Creates a parser for this program.

    Args:
        config_file (): The path to this programs config file (will be created if it
        does not exist)

    Returns:
        The :py:class:`argparse.ArgumentParser` for this program

    """
    parser = FileListingArgParse(
        prog=PROGRAM_NAME,
        description="Scrapes URLs of recipes into text files",
        epilog=(
            "Change the default-values for these options by modifying the"
            f" '{PROGRAM_NAME}.toml'file mentioned below."
        ),
    )

    arg_config = ArgConfig(parser, config_file)

    arg_config.add_narg("url", "URLs whose recipes should be added to the recipe-file")
    arg_config.add_narg(
        "--file",
        "Text-files containing URLs whose recipes should be added to the recipe-file",
    )
    arg_config.add_arg(
        "--output",
        "Specifies an output file. THIS WILL OVERWRITE ANY EXISTING FILE WITH THE SAME"
        " NAME.",
        default=get_default_output(),
    )
    arg_config.add_choice(
        "--verbosity",
        "Sets the 'chattiness' of the program",
        choices=get_args(LOG_LEVEL_NAMES),
        default="critical",
    )
    arg_config.add_type(
        "--connections",
        default=Fetcher.connections,
        short="-con",
        help_str=(
            f"{AIOHTTP_NOT_AVAILABLE_MSG}Sets the number of simultaneous connections"
        ),
    )
    arg_config.add_choice(
        "--cache",
        choices=["only", "new", "default"],
        default="default",
        help_str=(
            "Controls how the program should handle its cache: With 'only' no new data"
            " will be downloaded, the recipes will be generated from data that has been"
            " downloaded previously. If a recipe is not in the cache, it will not be"
            " written into the final output. 'new' will make the program ignore any"
            " saved data and download the requested recipes even if they have already"
            " been downloaded. Old data will be replaced by the new version, if it is"
            " available. The 'default' will fetch and merge missing data with the data"
            " already saved, only inserting new data into the cache where there was"
            " none previously."
        ),
    )
    arg_config.add_bool(
        "--debug", "Activates debug-mode: Changes the directory for application data"
    )
    arg_config.add_type(
        "--timeout",
        default=Fetcher.timeout,
        help_str=(
            "Sets the number of seconds the program waits for an individual website to"
            f" respond, eg. {WHICH_VALUE_SET_MSG}"
        ),
    )
    arg_config.add_choice(
        "--output-format",
        choices=get_template_files().keys(),
        default="txt",
        help_str=(
            "Sets the format for the output-file. The value defines which"
            " .jinja-template will be used to format the file. The templates are"
            f" available under '{JINJA_TEMPLATE_DIR}'."
        ),
    )
    arg_config.add_arg(
        "--user-agent",
        "Sets the user-agent to be used for the requests.",
        default=Fetcher.user_agent,
    )
    arg_config.add_bool(
        "--erase-appdata",
        "Erases all data- and cache-files (e.g. the files listed below)",
        short=None,
    )
    arg_config.add_bool(
        "--version",
        "Displays the version number (SemVer)",
        short=None,
    )

    return parser


@cache
def get_parser() -> argparse.ArgumentParser:
    return config_args(CONFIG_FILE)


def mutex_args(a: argparse.Namespace) -> None:
    """
    Responsible for handling '--erase-appdata' and '--version'

    Raises:
        SystemExit:
            with error code: when another parameter was passed with '--erase-appdata'
            without error code: when the program-data was erased successfully

    Args:
        a: The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
    """
    if a.erase_appdata:
        if len(sys.argv) > 2:
            get_parser().error("--erase-appdata cannot be used with any other flags")
        erase_files()
        sys.exit(os.EX_OK)
    if a.version:
        if len(sys.argv) > 2:
            get_parser().error("--version cannot be used with any other flags")
        if not PYPROJECT.is_file():
            print("pyproject.toml-file not found", sys.stderr)
            sys.exit(os.EX_IOERR)
        with PYPROJECT.open("rb") as pyproject:
            toml = tomllib.load(pyproject)
            version = toml["project"]["version"]

        print(version)
        sys.exit(os.EX_OK)


def init_logging(debug: bool, verbosity: str) -> None:
    """
    Initializes the global logger
    Args:
        debug (): Whether the logger operates in debug-mode (affects placement of log files)
        verbosity (): The verbosity of the logger
    """
    log_file = get_log(debug)
    root_log_setup(STRING2LEVEL[verbosity], str(log_file))


def sancheck_args(a: argparse.Namespace) -> None:
    """
    Responsible for quickly verifying certain parameters.

    Args:
        a: The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
    """
    if not (a.file or a.url):
        get_parser().error("Nothing to process: No file or url passed")
    if a.connections < 1:
        logger.warning("Number of connections smaller than 1, setting to 1 ")
        a.connections = 1
    elif a.connections > 1 and not Fetcher.is_async:
        logger.warning(  # type: ignore[unreachable]
            "Number of connections greater than 1, but package aiohttp not installed."
        )
    if a.timeout <= 0.0:
        logger.warning("Network timeout equal to or smaller than 0, setting to 0.1")
        a.timeout = 0.1

    if CONFIG_FILE.stat().st_size == 0:
        logger.warning("The config-file %s is empty", CONFIG_FILE)


def init_database(debug: bool, out: File) -> Database:
    """
    Initializes the cache-database for the program
    Args:
        debug (): Whether the database operates in debug-mode
        out (): The file the recipes will be written to during this session

    Returns:
        A database
    """
    db_file = get_db(debug)
    return Database(db_file, out)


def strings2urls(
    url_str: list[str], files: list[str], counts: Counts | None = None
) -> set[URL]:
    """
    Converts the input-strings to urls


    Args:
        url_str (): strings that could contain urls
        files (): potential paths to files that contain urls
        counts (): a counter to keep track of the sum of strings fed into the program

    Returns:
        All strings that could be identified as urls
    """
    strings = url_str + read_files(*files)
    urls = extract_urls(strings)
    if not urls:
        logger.critical("No valid URL passed")
        sys.exit(os.EX_DATAERR)
    if counts:
        counts.strings = len(strings)
    return urls
