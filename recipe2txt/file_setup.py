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
    RECIPES_NAME (Final[LiteralString]): name of the default output-file all the collected recipes will be written
    to
    DEFAULT_URLS_NAME (Final[LiteralString]): name of the default file that the urls will be read from (if no other
    urls are specified via CLI-arguments
    DEFAULT_OUTPUT_LOCATION_NAME (Final[LiteralString]): name of the config-file used to store the default
    output-location
    how_to_report_txt (Final[LiteralString]): help-text describing how to report errors arising from the external
    :py:mod:`recipe-scrapers`
"""
import os
import sys
import textwrap
from shutil import rmtree
from typing import Final, Tuple, Literal, NamedTuple
from pathlib import Path

from xdg_base_dirs import xdg_data_home, xdg_config_home, xdg_state_home

from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.html2recipe import errors2str
from recipe2txt.sql import AccessibleDatabase, ensure_accessible_db_critical
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import ensure_existence_dir, ensure_accessible_file_critical, File, Directory, full_path, \
    create_timestamped_dir

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
DEFAULT_URLS_NAME: Final[LiteralString] = "urls.txt"
"""name of the default file that the urls will be read from (if no other urls are specified via CLI-arguments"""
DEFAULT_OUTPUT_LOCATION_NAME: Final[LiteralString] = "default_output_location.txt"
"""name of the config-file used to store the default output-location"""


def file_setup(debug: bool = False, output: str = "", markdown: bool = False) -> Tuple[AccessibleDatabase, File, File]:
    """
    Initializes all files that the program will need to read from and write to.

    Args:
        debug (): Whether the default- or the debug-directories should be used
        output (): Where the recipes should be written to (will use the location provided by
        :py:data:`DEFAULT_OUTPUT_LOCATION_NAME' if not set or fallback to the current working directory if nothing is
        configured
        markdown ():Whether the output-file is a plain text- or a Markdown-file
    Returns:
        A tuple consisting of the path to (1) the database, (2) the output-file and (3) the log-file the program will
        use.
    Raises:
        SystemExit (): When one of the files cannot be created/accessed by the program.
    """
    directory = debug_dirs if debug else default_dirs

    db_file = ensure_accessible_db_critical(directory.data, DB_NAME)
    log_file = ensure_accessible_file_critical(directory.state, LOG_NAME)

    if output:
        output_file = ensure_accessible_file_critical(output)
    else:
        output_file = get_default_output(directory.config, markdown)

    return db_file, output_file, log_file


def get_files(debug: bool = False) -> list[str]:
    """
    Lists all program files.

    Args:
        debug (): Only list the files in the debug directories
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
        debug (): Only delete the debug-version of those directories.
    """
    directories = list(debug_dirs)
    directories = directories if debug else directories + list(default_dirs)

    for directory in directories:
        if directory.is_dir():
            logger.warning("Deleting %s", directory)
            rmtree(directory)


def get_default_output(config_path: Path, markdown: bool) -> File:
    """
    Get the file that the program should write recipes to when no file has been specified by the CLI-arguments.

    This is either a file preconfigured by the user or a file in the currend working directory.
    Args:
        config_path (): The path to the programs configuration files
        markdown (): Whether the file should be a txt- or a markdown-file
    Returns:
        A path to an existing file to write recipes to.
    Raises:
        SystemExit (): Raised, when the :py:data:`DEFAULT_OUTPUT_LOCATION_NAME`-file is not in the correct format or
        when the output-file cannot be created/accessed.

    """
    output_location_file = config_path / DEFAULT_OUTPUT_LOCATION_NAME
    if output_location_file.is_file():
        text = output_location_file.read_text().split(os.linesep)
        text = [line for line in text if line]
        if len(text) != 2:
            logger.error(f"The config file ({output_location_file}) has unexpected content.")
            sys.exit(os.EX_DATAERR)
        output = text[1] if markdown else text[0]
        output_file = ensure_accessible_file_critical(output)
    else:
        recipes_name = RECIPES_NAME_MD if markdown else RECIPES_NAME_TXT
        output_file = ensure_accessible_file_critical(Directory(Path.cwd()), recipes_name)
    return output_file


def set_default_output(filepath: str | Literal["RESET"], debug: bool = False) -> None:
    """
    Sets the path to the file that the program should write recipes to.

    This function is called when no file has been specified by the CLI-arguments.
    Args:
        filepath (): Either a new path for the default-file or the string literal "RESET", which will erase any existing
         path.
        debug (): Whether the normal or the debug configuration file should be manipulated.
    """
    data_dir = debug_dirs.config if debug else default_dirs.config
    if filepath == "RESET":
        try:
            os.remove(data_dir / DEFAULT_OUTPUT_LOCATION_NAME)
            logger.warning("Removed default output location. When called without specifying the output-file recipes"
                           " will now be written in the current working directory with the name %s", RECIPES_NAME_TXT)
        except FileNotFoundError:
            logger.warning("No default output set")
        except OSError as e:
            logger.error("Error while deleting file %s: %s", filepath, getattr(e, 'message', repr(e)))
            sys.exit(os.EX_IOERR)
    else:
        config_file = ensure_accessible_file_critical(data_dir, DEFAULT_OUTPUT_LOCATION_NAME)

        path = full_path(filepath)
        path_txt = path.with_suffix(".txt")
        path_md = path.with_suffix(".md")

        new_config = f"{path_txt}{os.linesep}{path_md}{os.linesep}"
        config_file.write_text(new_config)
        logger.warning(f"Set default output location to {path_txt}, {path_md}")


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
        debug (): Whether the reports should be written into the normal- or into the debug-state-directory

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
