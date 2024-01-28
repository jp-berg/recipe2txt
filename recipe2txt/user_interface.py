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
import logging
import os
import sys
import textwrap
from functools import cache
from pathlib import Path
from typing import Final, Tuple, get_args

from recipe2txt.fetcher import Cache
from recipe2txt.file_setup import (
    CONFIG_FILE,
    PROGRAM_NAME,
    erase_files,
    get_db,
    get_default_output,
    get_files,
    get_log,
)
from recipe2txt.utils.ArgConfig import ArgConfig
from recipe2txt.utils.ContextLogger import (
    LOG_LEVEL_NAMES,
    STRING2LEVEL,
    get_logger,
    root_log_setup,
)
from recipe2txt.utils.misc import (
    URL,
    Counts,
    File,
    dict2str,
    ensure_accessible_file_critical,
    extract_urls,
    read_files,
)

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
            os.linesep + "  " + (os.linesep + "  ").join(files) if files else " none"
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
    arg_config.add_bool("--markdown", "Generates markdown-output instead of '.txt'")
    arg_config.add_arg(
        "--user-agent",
        "Sets the user-agent to be used for the requests.",
        default=Fetcher.user_agent,
    )
    arg_config.add_arg(
        "--erase-appdata",
        "Erases all data- and cache-files (e.g. the files listed below)",
        short=None,
    )

    return parser


@cache
def get_parser() -> argparse.ArgumentParser:
    return config_args(CONFIG_FILE)


def mutex_args(a: argparse.Namespace) -> None:
    """
    Responsible for handling '--erase-appdata'.

    Raises:
        SystemExit:
            with error code: when another parameter was passed with '--erase-appdata'
            without error code: when the program-data was erased successfully

    Args:
        a: The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
    """
    if not a.erase_appdata:
        return
    if len(sys.argv) > 2:
        get_parser().error("--erase-appdata cannot be used with any other flags")
    erase_files()
    sys.exit(os.EX_OK)


def sancheck_args(a: argparse.Namespace, output: File) -> None:
    """
    Responsible for quickly verifying certain parameters.

    Args:
        a: The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`
        output: The output file the recipes will be written to.
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

    ext = output.suffix
    if a.markdown:
        if ext != ".md":
            logger.warning(
                "The application is instructed to output a markdown file, but the"
                " filename extension indicates otherwise:'%s'",
                ext,
            )
    else:
        if ext not in ("", ".txt"):
            logger.warning(
                "The application is instructed to output a text file, but the filename"
                " extension indicates otherwise:'%s'",
                ext,
            )
    if output.stat().st_size > 0:
        logger.warning("The output-file already exists. It will be overwritten.")

    if CONFIG_FILE.stat().st_size == 0:
        logger.warning("The config-file %s is empty", CONFIG_FILE)


def process_params(a: argparse.Namespace) -> Tuple[set[URL], Fetcher]:
    """
    Responsible for  using the CLI-flags to construct a valid
    :py:class:`recipe2txt.fetcher_abstract.AbstractFetcher`

    Args:
        a: The result of a call to :py:method:`argparse.ArgumentParser.parse_args()`

    Returns:
        A tuple of:
            A set of all possible urls gathered from the CLI-arguments.
            An :py:class:`recipe2txt.fetcher_abstract.AbstractFetcher`, initialized
            with the validated parameters
            gathered from :py:mod:`argparse`

    """
    log_file = get_log(a.debug)
    root_log_setup(STRING2LEVEL[a.verbosity], str(log_file))

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "CLI-ARGS: %s\t%s", os.linesep, dict2str(vars(a), os.linesep + "\t")
        )

    logger.info("--- Preparing arguments ---")

    db_file = get_db(a.debug)
    recipe_file = ensure_accessible_file_critical(a.output)
    logger.info("Output set to: %s", recipe_file)

    sancheck_args(a, recipe_file)

    unprocessed: list[str] = read_files(*a.file)
    unprocessed += a.url
    processed: set[URL] = extract_urls(unprocessed)
    if not processed:
        logger.critical("No valid URL passed")
        sys.exit(os.EX_DATAERR)

    counts = Counts()
    counts.strings = len(unprocessed)

    f = Fetcher(
        output=recipe_file,
        connections=a.connections,
        counts=counts,
        database=db_file,
        timeout=a.timeout,
        markdown=a.markdown,
        cache=Cache(a.cache),
    )

    return processed, f
