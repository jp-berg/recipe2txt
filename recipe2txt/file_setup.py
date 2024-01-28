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
Handles most file- and data-operations of the program aside from writing the recipes
to the output-file.

Attributes:
    logger (logging.Logger): The logger for the module. Receives the constructed
        logger from :py:mod:`recipe2txt.utils.ContextLogger`
    DEFAULT_DIRS (Final[ProgramDirectories]): Specifies the paths the program will
    use during normal operation for
        storage of data, configuration-files and state. The specified paths try to
        adhere to the XDG Base Directory Specification
    DEBUG_DIRECTORY_BASE (Final[Path]): Specifies the root directory for all files
    used by this program when the
        '--debug'-flag is set.
    DEBUG_DIRS (Final[ProgramDirectories]): Specifies the paths the program will use
        when the '--debug'-flag is set. The directories (data, config, state) mirror
        their :py:data:`default-dirs` counterparts in function.
    LOG_NAME (Final[LiteralString]): name of the log-file the loggers of this program
        will write to
    DB_NAME (Final[LiteralString]): name of the sqlite-database-file used by this
        program
    RECIPES_NAME (Final[LiteralString]): name of the default output-file all the
    collected recipes will be written to
"""
import os
import textwrap
from pathlib import Path
from shutil import rmtree
from typing import Final, NamedTuple

from xdg_base_dirs import xdg_config_home, xdg_data_home, xdg_state_home

from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import (
    AccessibleDatabase,
    Directory,
    File,
    create_timestamped_dir,
    ensure_accessible_db_critical,
    ensure_accessible_file_critical,
    ensure_existence_dir,
)

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from 
:py:mod:`recipe2txt.utils.ContextLogger`"""

PROGRAM_NAME: Final = "recipes2txt"


class ProgramDirectories(NamedTuple):
    """
    A tuple of three paths

    The paths describe storage locations for program data, configuration and state,
    ideally in line with
    the XDG Base Directory Specification (see
    specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
    """

    data: Path
    config: Path
    state: Path


DEFAULT_DIRS: Final = ProgramDirectories(
    xdg_data_home() / PROGRAM_NAME,
    xdg_config_home() / PROGRAM_NAME,
    xdg_state_home() / PROGRAM_NAME,
)
"""
Specifies the paths the program will use during normal operation for storage of data, 
configuration-files and state. 
        
The specified paths try to adhere to the XDG Base Directory Specification.
"""

DEBUG_DIRECTORY_BASE: Final = (
    Path(__file__).parents[1] / "test" / "testfiles" / "debug-dirs"
)

"""Specifies the root directory for all files used by this program when the 
'--debug'-flag is set."""

DEBUG_DIRS: Final = ProgramDirectories(
    DEBUG_DIRECTORY_BASE / "data",
    DEBUG_DIRECTORY_BASE / "config",
    DEBUG_DIRECTORY_BASE / "state",
)
"""
Specifies the paths the program will use when the '--debug'-flag is set.

The directories (data, config, state) mirror their :py:data:`default-dirs` 
counterparts in function.
"""

LOG_NAME: Final = "debug.log"
"""name of the log-file the loggers of this program will write to"""
DB_NAME: Final = PROGRAM_NAME + ".sqlite3"
"""name of the sqlite-database-file used by this program"""
CONFIG_NAME: Final = PROGRAM_NAME + ".toml"
"""name of the config-file that provides the default values for options"""
RECIPES_NAME: Final = "recipes"
"""name of the default output-file all the collected recipes will be written to"""
RECIPES_NAME_TXT: Final = RECIPES_NAME + ".txt"
RECIPES_NAME_MD: Final = RECIPES_NAME + ".md"
CONFIG_FILE: Final = DEFAULT_DIRS.config / CONFIG_NAME
"""path to the config-file"""
HOW_TO_REPORT_NAME: Final = "how_to_report_errors.txt"
"""Name of the file containing instructions on how to report recipe_scrapers-errors"""


def get_default_output() -> str:
    """
    Get the default output file.

    Returns:
        A path to a text-file in the current working directory.

    """
    return os.path.join(os.getcwd(), RECIPES_NAME)


def get_db(debug: bool = False) -> AccessibleDatabase:
    """
    Returns the default database

    Creates the database-file, if none is found

    Args:
        debug (): Whether the standard- or the debug-folders should be used.

    Returns:
        The database

    Raises:
        SystemExit: When the database cannot be created/accessed
    """
    directory = DEBUG_DIRS.data if debug else DEFAULT_DIRS.data
    return ensure_accessible_db_critical(directory, DB_NAME)


def get_log(debug: bool = False) -> File:
    """
    Returns the default log-file

    Creates the log-file, if none is found

    Args:
        debug (): Whether the standard- or the debug-folders should be used.

    Returns:
        The log-file

    Raises:
        SystemExit: When the log-file cannot be created/accessed

    """
    directory = DEBUG_DIRS.state if debug else DEFAULT_DIRS.state
    return ensure_accessible_file_critical(directory, LOG_NAME)


def get_files(debug: bool = False) -> list[str]:
    """
    Lists all program files.

    Args:
        debug: Only list the files in the debug directories

    Returns:
        A list of absolute paths pointing towards all the program files
    """
    directories = list(DEBUG_DIRS)
    directories = directories if debug else directories + list(DEFAULT_DIRS)
    files = [
        str(file)
        for directory in directories
        if directory.is_dir()
        for file in directory.iterdir()
    ]
    return files


def erase_files(debug: bool = False) -> None:
    """
    Deletes the data-, config- and state-directories used by this program (and thus
    the program files).

    Args:
        debug: Only delete the debug-version of those directories.
    """
    directories = list(DEBUG_DIRS)
    directories = directories if debug else directories + list(DEFAULT_DIRS)

    for directory in directories:
        if directory.is_dir():
            logger.warning("Deleting %s", directory)
            rmtree(directory)


HOW_TO_REPORT_TXT: Final = textwrap.dedent(
    """
    During its execution the program encountered errors while trying to scrape 
    recipes. In cases where the error seems to originate from the underlying library 
    'recipe-scrapers' an error-report per error has been generated and saved to a file.
    You find those files in the folders adjacent to this file. There is one folder 
    per error-encountering execution of the program (named with the timestamp of the
    moment the execution finished: 'Year-Month-Day_Hour-Minute-Second').
    If you want those errors fixed, go to 
    'https://github.com/hhursev/recipe-scrapers/issues' and search for each filename
    (without the '.md'-extension). If you cannot find a matching report for a filename, 
    please click 'New Issue' and select 'Scraper Bug Report'. Paste the filename
    (without the '.md'-extension) into the 'Title'-Field and the contents of the file
    into the 'Write'-field. Check the 'Pre-filling  checks'-boxes ONLY if you made 
    sure to follow their instructions. After that click 'Submit new issue'. 
    The maintainers of the library will have a look at your problem and try to fix
    it. 
    Please note that they are volunteers and under no obligation to help you. Be kind
    to them.
    """
)
"""Text describing how to report errors originating from the 
:py:mod:`recipe-scrapers`-library."""


def get_parsing_error_dir(debug: bool = False) -> Directory | None:
    data_path = DEBUG_DIRS.state if debug else DEFAULT_DIRS.state
    if not (error_dir := ensure_existence_dir(data_path, "error_reports")):
        logger.error(
            "Could not create %s, no reports will be written",
            data_path / "error_reports",
        )
        return None

    how_to_report_file = error_dir / HOW_TO_REPORT_NAME
    if not how_to_report_file.is_file():
        how_to_report_file.write_text(HOW_TO_REPORT_TXT)

    current_error_dir = create_timestamped_dir(error_dir)
    if not current_error_dir:
        logger.error(
            "Could not create directory for error reporting, no reports will be"
            " written."
        )
        return None

    return current_error_dir
