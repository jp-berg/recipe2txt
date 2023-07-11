import os
import sys
from shutil import rmtree
from time import strftime, gmtime
from typing import Final, Tuple, Literal

from xdg_base_dirs import xdg_data_home

from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.html2recipe import errors2str
from recipe2txt.sql import AccessibleDatabase, ensure_accessible_db_critical
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import ensure_existence_dir, ensure_accessible_file_critical, File, Directory

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
    db_file = ensure_accessible_db_critical(DB_NAME, data_path)
    log_file = ensure_accessible_file_critical(LOG_NAME, data_path)

    if output:
        output = ensure_accessible_file_critical(output)
    else:
        if debug:
            output_location_file = os.path.join(DEBUG_DATA_DIRECTORY, DEFAULT_OUTPUT_LOCATION_NAME)
        else:
            output_location_file = os.path.join(DEFAULT_DATA_DIRECTORY, DEFAULT_OUTPUT_LOCATION_NAME)
        if os.path.isfile(output_location_file):
            with open(output_location_file, 'r') as file:
                output = file.readline().rstrip(os.linesep)
                if markdown:
                    output = file.readline().rstrip(os.linesep) # SOLLTE DAS FÜR MARKDOWN UND TXT NICHT GLEICH SEIN?
            output = ensure_accessible_file_critical(output)
        else:
            if markdown:
                recipes_name = RECIPES_NAME_MD
            else:
                recipes_name = RECIPES_NAME_TXT
            output = ensure_accessible_file_critical(recipes_name, Directory(os.getcwd()))

    return db_file, output, log_file


def show_files() -> None:
    files = []
    if os.path.isdir(DEFAULT_DATA_DIRECTORY):
        files = [os.path.join(DEFAULT_DATA_DIRECTORY, file) for file in os.listdir()]

    files_debug = []
    if os.path.isdir(DEBUG_DATA_DIRECTORY):
        files_debug = [os.path.join(DEBUG_DATA_DIRECTORY, file) for file in os.listdir(DEBUG_DATA_DIRECTORY)]

    files += files_debug
    if files:
        print(*files, sep=os.linesep)
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
               f"that could not be (completely) scraped.{os.linesep}" \
               f" Please see {os.linesep}%s{os.linesep}if you want to help fix this."
    logger.warning(warn_msg, how_to_report_file)

    return len(errors)
