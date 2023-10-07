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
Handles all file- and data-operations of the program aside from writing the recipes to the output-file.

Attributes:
    logger (logging.Logger): The logger for the module. Receives the constructed logger from
        :py:mod:`recipe2txt.utils.ContextLogger`
    default_dirs (Final[ProgramDirectories]): Specifies the paths the program will use during normal operation for
        storage of data, configuration-files and state. The specified paths try to adhere to the XDG Base Directory
        Specification
    DEBUG_DIRECTORY_BASE (Final[Path]): Specifies the root directory for all files used by this program when the
        '--debug'-flag is set.
    debug_dirs (Final[ProgramDirectories]): Specifies the paths the program will use when the '--debug'-flag is set.
    The directories (data, config, state) mirror their :py:data:`default-dirs` counterparts in function.
    LOG_NAME (Final[LiteralString]): name of the log-file the loggers of this program will write to
    DB_NAME (Final[LiteralString]): name of the sqlite-database-file used by this program
    RECIPES_NAME (Final[LiteralString]): name of the default output-file all the collected recipes will be written to
    how_to_report_txt (Final[LiteralString]): help-text describing how to report errors arising from the external
        :py:mod:`recipe-scrapers`
"""
import os
import textwrap
from pathlib import Path
from shutil import rmtree
from typing import Final, Tuple, NamedTuple

from xdg_base_dirs import xdg_data_home, xdg_config_home, xdg_state_home

from recipe2txt.html2recipe import errors2str
from recipe2txt.sql import AccessibleDatabase, ensure_accessible_db_critical
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.utils.misc import ensure_existence_dir, ensure_accessible_file_critical, File, create_timestamped_dir

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from :py:mod:`recipe2txt.utils.ContextLogger`"""

PROGRAM_NAME: Final[LiteralString] = "recipes2txt"


class ProgramDirectories(NamedTuple):
    """
    A tuple of three paths

    The paths describe storage locations for program data, configuration and state, ideally in line with
    the XDG Base Directory Specification (see specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
    """
    data: Path
    config: Path
    state: Path


default_dirs: Final[ProgramDirectories] = ProgramDirectories(xdg_data_home() / PROGRAM_NAME,
                                                             xdg_config_home() / PROGRAM_NAME,
                                                             xdg_state_home() / PROGRAM_NAME)
"""
Specifies the paths the program will use during normal operation for storage of data, configuration-files and state. 
        
The specified paths try to adhere to the XDG Base Directory Specification.
"""

DEBUG_DIRECTORY_BASE: Final[Path] = Path(__file__).parents[1] / "test" / "testfiles" / "debug-dirs"
"""Specifies the root directory for all files used by this program when the '--debug'-flag is set."""

debug_dirs: Final[ProgramDirectories] = ProgramDirectories(DEBUG_DIRECTORY_BASE / "data",
                                                           DEBUG_DIRECTORY_BASE / "config",
                                                           DEBUG_DIRECTORY_BASE / "state")
"""
Specifies the paths the program will use when the '--debug'-flag is set.

The directories (data, config, state) mirror their :py:data:`default-dirs` counterparts in function.
"""

LOG_NAME: Final[LiteralString] = "debug.log"
"""name of the log-file the loggers of this program will write to"""
DB_NAME: Final[LiteralString] = PROGRAM_NAME + ".sqlite3"
"""name of the sqlite-database-file used by this program"""
RECIPES_NAME: Final[LiteralString] = "recipes"
"""name of the default output-file all the collected recipes will be written to"""
RECIPES_NAME_TXT: Final[LiteralString] = RECIPES_NAME + ".txt"
RECIPES_NAME_MD: Final[LiteralString] = RECIPES_NAME + ".md"


def get_default_output() -> str:
    """
    Get the default output file.

    Returns:
        A path to a text-file in the current working directory.

    """
    return os.path.join(os.getcwd(), RECIPES_NAME)


def file_setup(output: str, debug: bool = False) -> Tuple[AccessibleDatabase, File, File]:
    """
    Initializes all files that the program will need to read from and write to.

    Args:
        debug: Whether the default- or the debug-directories should be used
        output: Where the recipes should be written to (will use the location provided by
            :py:data:`DEFAULT_OUTPUT_LOCATION_NAME' if not set or fallback to the current working directory if nothing
            is configured)

    Returns:
        A tuple consisting of the path to (1) the database, (2) the output-file and (3) the log-file the program will
        use.

    Raises:
        SystemExit: When one of the files cannot be created/accessed by the program.
    """
    directory = debug_dirs if debug else default_dirs

    output_file = ensure_accessible_file_critical(output)

    db_file = ensure_accessible_db_critical(directory.data, DB_NAME)
    log_file = ensure_accessible_file_critical(directory.state, LOG_NAME)

    return db_file, output_file, log_file


def get_files(debug: bool = False) -> list[str]:
    """
    Lists all program files.

    Args:
        debug: Only list the files in the debug directories

    Returns:
        A list of absolute paths pointing towards all the program files
    """
    directories = list(debug_dirs)
    directories = directories if debug else directories + list(default_dirs)
    files = [str(file) for directory in directories if directory.is_dir()
             for file in directory.iterdir()]
    return files


def erase_files(debug: bool = False) -> None:
    """
    Deletes the data-, config- and state-directories used by this program (and thus the program files).

    Args:
        debug: Only delete the debug-version of those directories.
    """
    directories = list(debug_dirs)
    directories = directories if debug else directories + list(default_dirs)

    for directory in directories:
        if directory.is_dir():
            logger.warning("Deleting %s", directory)
            rmtree(directory)


how_to_report_txt: Final[LiteralString] = textwrap.dedent(
    """During its execution the program encountered errors while trying to scrape recipes.
    In cases where the error seems to originate from the underlying library 'recipe-scrapers' an error-report per error
    has been generated and saved to a file.
    You find those files in the folders adjacent to this file. There is one folder per error-encountering excecution of
    the program (naming format: 'Year-Month-Day_Hour-Minute-Second' when finishing execution). If you want those errors
    fixed, go to 'https://github.com/hhursev/recipe-scrapers/issues' and search for each filename (without the 
    '.md'-extension). If you cannot find a matching report for a filename, please click 'New Issue' and select 'Scraper 
    Bug Report'. Paste the filename (without the '.md'-extension) into the 'Title'-Field and the contents of the file
    into the 'Write'-field. Check the 'Pre-filling  checks'-boxes ONLY if you made sure to follow their instructions. 
    After that click 'Submit new issue'. The maintainers of the library will have a look at your problem and try to fix
    it. Please note that they are volunteers and under no obligation to help you. Be kind to them.
    """)
"""Text describing how to report errors originating from the :py:mod:`recipe-scrapers`-library."""


def write_errors(debug: bool = False) -> int:
    """
    Writes the error reports from :py:func:`recipe2txt.html2recipe.errors2str` to a timestamped directory.

    Args:
        debug: Whether the reports should be written into the normal- or into the debug-state-directory

    Returns:
        Number of errors written

    """
    if not (errors := errors2str()):
        return 0

    logger.info("---Writing error reports---")

    data_path = debug_dirs.state if debug else default_dirs.state
    if not (error_dir := ensure_existence_dir(data_path, "error_reports")):
        logger.error("Could not create %s, no reports will be written", data_path / "error_reports")
        return 0
    how_to_report_file = error_dir / "how_to_report_errors.txt"
    if not how_to_report_file.is_file():
        how_to_report_file.write_text(how_to_report_txt)

    current_error_dir = create_timestamped_dir(error_dir)
    if not current_error_dir:
        logger.error("Could not create directory for error reporting, no reports will be written.")
        return 0

    for title, msg in errors:
        filename = (current_error_dir / title).with_suffix(".md")
        filename.write_text(msg)

    warn_msg = f"During its execution the program encountered recipes " \
               f"that could not be (completely) scraped.{os.linesep}" \
               f"Please see {os.linesep}%s{os.linesep}if you want to help fix this."
    logger.warning(warn_msg, how_to_report_file)

    return len(errors)
