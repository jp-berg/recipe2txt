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

import argparse
import os
import random
import shutil
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path
from test.test_helpers import TEST_PROJECT_TMPDIR
from typing import Final, Literal, TypeAlias, get_args

from recipe2txt.file_setup import DB_NAME, DEBUG_DIRS, LOG_NAME
from recipe2txt.utils.ContextLogger import LOG_LEVEL_NAMES
from recipe2txt.utils.misc import (
    Directory,
    create_timestamped_dir,
    ensure_accessible_file_critical,
)


def escape_whitespace(element: str) -> str:
    if " " in element:
        if not (element.startswith("'") and element.endswith("'")):
            element = f"'{element}'"
    return element


def path2str(path: Path) -> str:
    p = str(path)
    if " " in p:
        elements = path.parts
        elements_esc = [escape_whitespace(element) for element in elements]
        p = os.path.join(os.sep, *elements_esc)
    return p


TEST_DIR: Final = Path(__file__).parent
WORK_DIR: Final = TEST_DIR.parent
TEST_FILES: Final = TEST_DIR / "testfiles"
PROGRAM_NAME: Final = "test4recipe2txt"
URLS_ORIGIN: Final = TEST_FILES / "permanent" / "all_urls.txt"
PYTHON_PATH: Final = WORK_DIR / ".venv" / "bin" / "python"
REPORTS: Final = TEST_DIR / "reports_test4recipe2txt"
URLS_SHUFFLED: Final = REPORTS / "urls_shuffled.txt"
LOGFILE: Final = DEBUG_DIRS.state / LOG_NAME
ERROR_DIR: Final = DEBUG_DIRS.state / "error_reports"
DB_FILE: Final = DEBUG_DIRS.data / DB_NAME
RE2TXT: Final[list[str]] = [path2str(PYTHON_PATH), "-m", "recipe2txt.re2txt"]


def check_existence(path: Path) -> None:
    if not path.is_file():
        print(f"Does not exist: {path}", file=sys.stderr)
        sys.exit(os.EX_IOERR)


def time2str(t: float) -> str:
    return time.strftime("%x - %X", time.localtime(t))


def copy_testrun_data(origin: Path, dest: Directory, min_time: float) -> None:
    if not origin.exists():
        print(f"{origin} was not generated", file=sys.stderr)
        return
    elif min_time > (mt := os.path.getmtime(origin)):
        print(
            f"{origin} is probably too old to originate from this testrun (execution"
            f" started {time2str(min_time)}, but time of last modification is"
            f" {time2str(mt)}",
            file=sys.stderr,
        )
    else:
        if origin.is_file():
            shutil.copy2(origin, dest / origin.name)
        else:
            shutil.copytree(origin, dest / origin.name)


def get_urls() -> list[str]:
    urls = [url for url in URLS_ORIGIN.read_text().split(os.linesep) if url]
    if not URLS_SHUFFLED.is_file():
        urls_shuffled = urls
        random.shuffle(urls_shuffled)
    else:
        origin = set(urls)
        od_list = [
            (url, None) for url in URLS_SHUFFLED.read_text().split(os.linesep) if url
        ]
        shuffled = OrderedDict(od_list)
        to_add = origin - shuffled.keys()
        to_remove = shuffled.keys() - origin

        for elem in to_add:
            shuffled[elem] = None
        for elem in to_remove:
            shuffled.pop(elem)
        urls_shuffled = list(shuffled.keys())

    return urls_shuffled


parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME, description="End-to-end testing for recipe2txt."
)

FileFormatValues: TypeAlias = Literal["txt", "md", "both"]
InputFormatValues: TypeAlias = Literal["url", "file"]

parser.add_argument(
    "-urls",
    "--number-of-urls",
    type=int,
    default=5,
    help=(
        "Set the number of urls to test. Default is 5, using a number outside of the"
        " number of available urls will run a test with all urls."
    ),
)
parser.add_argument(
    "-con",
    "--connections",
    type=int,
    default=0,
    help=(
        "Set the number of connections to be used. 1 will run the test in synchronous"
        " mode, 0 or less will use one connection per url (default is 0)"
    ),
)
parser.add_argument(
    "-dd",
    "--delete-database",
    action="store_true",
    help="Delete the test-database before the testrun.",
)
parser.add_argument(
    "-v",
    "--verbosity",
    default="info",
    choices=get_args(LOG_LEVEL_NAMES),
    help="Set the logging verbosity.",
)
parser.add_argument(
    "-f",
    "--file-format",
    choices=get_args(FileFormatValues),
    default="txt",
    help="Which type of file should the testrun generate. (default is 'txt')",
)
parser.add_argument(
    "-i",
    "--input-format",
    choices=get_args(InputFormatValues),
    default="url",
    help="Which type of input format should the program recieve (default is 'url')",
)
parser.add_argument(
    "-l",
    "--long-timeout",
    action="store_true",
    help="If used, the timeout is set to 20 seconds (default is 10)",
)


def main(
    number_of_urls: int = 5,
    connections: int = 0,
    delete_database: bool = False,
    verbosity: LOG_LEVEL_NAMES = "info",
    file_format: FileFormatValues = "txt",
    input_format: InputFormatValues = "url",
    long_timeout: bool = False,
) -> None:
    os.chdir(WORK_DIR)
    check_existence(PYTHON_PATH)
    check_existence(URLS_ORIGIN)
    report_dir = create_timestamped_dir(REPORTS)
    if not report_dir:
        print("Reporting directory could not be created", file=sys.stderr)
        sys.exit(os.EX_IOERR)

    urls = get_urls()
    no_urls = len(urls) if number_of_urls < 0 else number_of_urls
    connections = no_urls if connections < 1 else connections
    timeout = 20 if long_timeout else 10

    test_urls = urls[:no_urls]
    args = [
        "--debug",
        "--connections",
        connections,
        "--timeout",
        timeout,
        "--verbosity",
        verbosity,
    ]

    output_file = report_dir / "output"
    if file_format == "md":
        args += ["--markdown", "--output", path2str(output_file.with_suffix(".md"))]
    else:
        args += ["--output", path2str(output_file.with_suffix(".txt"))]

    if input_format == "file":
        url_file = ensure_accessible_file_critical(TEST_PROJECT_TMPDIR, "urls.txt")
        url_file.write_text(os.linesep.join(test_urls))
        args += ["--file", path2str(url_file)]
    else:
        args += [*test_urls]

    if delete_database and DB_FILE.is_file():
        os.remove(DB_FILE)

    args_str = [str(arg) for arg in args]
    command = " ".join(RE2TXT) + " " + " ".join(args_str)
    (report_dir / "parameters.txt").write_text(command)
    (report_dir / "urls_used.txt").write_text(os.linesep.join(test_urls))

    print("+++ Running Test +++")
    start_time = time.time()
    result = subprocess.run(RE2TXT + args_str)
    print("+++ End Test +++")

    if result.stdout:
        (report_dir / "stdout").write_bytes(result.stdout)
    if result.stderr:
        (report_dir / "stderr").write_bytes(result.stderr)

    if result.returncode != 0:
        print(
            f"Return code not 0 ('{result.returncode}' ->"
            f" '{os.strerror(result.returncode)}')while executing{os.linesep}{command}",
            file=sys.stderr,
        )
        sys.exit(os.EX_USAGE)

    copy_testrun_data(LOGFILE, report_dir, start_time)
    copy_testrun_data(DB_FILE, report_dir, start_time)

    if ERROR_DIR.is_dir():
        current_error_dir = max(ERROR_DIR.iterdir(), key=os.path.getctime)
        copy_testrun_data(current_error_dir, report_dir, start_time)

    urls_to_write = urls[no_urls:] + test_urls
    URLS_SHUFFLED.write_text(os.linesep.join(urls_to_write))

    if TEST_PROJECT_TMPDIR.is_dir():
        shutil.rmtree(TEST_PROJECT_TMPDIR)

    shutil.make_archive(str(report_dir), "zip", report_dir)
    zip_file = report_dir.with_suffix(".zip")

    if zip_file.is_file():
        print(f"Test report available in {zip_file}")
        shutil.rmtree(report_dir)
    elif report_dir.is_dir():
        print(f"Test report available in {report_dir}")
    else:
        print(f"{report_dir} not available", file=sys.stderr)


if __name__ == "__main__":
    a = parser.parse_args()
    main(**vars(a))
    sys.exit(os.EX_OK)
