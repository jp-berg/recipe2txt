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

import getpass
import os
import unittest
from pathlib import Path
from shutil import rmtree
from tempfile import gettempdir
from typing import Any, Callable, Final

from xdg_base_dirs import xdg_data_home

import recipe2txt.html2recipe as h2r
import recipe2txt.utils.misc as misc
from recipe2txt.utils.ContextLogger import disable_loggers

disable_loggers()

__all__ = ["TEST_PROJECT_TMPDIR", "XDG_TMPDIR", "TMPDIR", "TMPDIR_NAME", "FILEDIR_NAME",
           "TEST_FILEDIR", "TMPDIRS", "create_tmpdirs", "delete_tmpdirs", "test_recipes",
           "assertAccessibleFile", "assertFilesEqual", "TESTFILE", "NORMAL_DIRS", "NONE_DIRS",
           "assertEval"]

TMPDIR_NAME: Final = "tmp_testfiles_re2txt"
FILEDIR_NAME: Final = "testfiles"

TEST_FILEDIR: Final = Path(__file__).parent / "testfiles"

TEST_PROJECT_TMPDIR: Final = Path(TEST_FILEDIR, TMPDIR_NAME)
XDG_TMPDIR: Final = Path(xdg_data_home(), TMPDIR_NAME)
TMPDIR: Final = Path(gettempdir(), TMPDIR_NAME)

TMPDIRS: Final[list[Path]] = [TEST_PROJECT_TMPDIR, XDG_TMPDIR, TMPDIR]

TESTDIRS: Final = ["TESTFOLDER1", "TESTFOLDER2"]
TESTFILE: Final = "TESTFILE.txt"

if getpass.getuser() == 'root':
    raise EnvironmentError("DO NOT RUN THESE TESTS AS ROOT-USER")
NONE_DIRS: Final = [[os.devnull] + TESTDIRS,
                    ["/root"] + TESTDIRS]
NORMAL_DIRS: Final = [[folder] + TESTDIRS for folder in TMPDIRS]

for directory in TMPDIRS:
    directory.mkdir(parents=True, exist_ok=True)


test_recipes: list[h2r.Recipe] = [
    h2r.Recipe(),
    h2r.Recipe(url=misc.URL("https://www.websitedown.com/recipe1"), status=h2r.RecipeStatus.UNREACHABLE,
               scraper_version=h2r.SCRAPER_VERSION),

    h2r.Recipe(title="Meal", host="incomplete_essential.com", url=misc.URL("https://www.incomplete.essential.com/meal"),
               status=h2r.RecipeStatus.INCOMPLETE_ESSENTIAL, scraper_version=h2r.SCRAPER_VERSION),

    h2r.Recipe(ingredients=os.linesep.join(["1 pinch of salt", "2 spoons of love", "1l water"]),
               instructions=os.linesep.join(["Gather", "Prepare", "Enjoy"]), title="Simple",
               yields="3 portions", url=misc.URL("https://www.notcomplete.net/simple"), host="notcomplete.net",
               status=h2r.RecipeStatus.INCOMPLETE_ON_DISPLAY, scraper_version=h2r.SCRAPER_VERSION),

    h2r.Recipe(ingredients=os.linesep.join(["Ingredient 1", "Ingredient 2", "Ingredient 3"]),
               instructions=os.linesep.join(["Step 1", "Step 2", "Step 3"]), title="Basic", total_time="123",
               yields="4 pieces", host="notcomplete.com", image="notcomplete.net/basic/img.basic-png",
               url=misc.URL("https://www.notcomplete.net/basic"), status=h2r.RecipeStatus.COMPLETE_ON_DISPLAY,
               scraper_version=h2r.SCRAPER_VERSION)
]


def create_tmpdirs() -> bool:
    res = True
    for directory in TMPDIRS:
        if not directory.is_dir():
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError:
                res = res and False
    return res


def delete_tmpdirs() -> bool:
    res = True
    for directory in TMPDIRS:
        if directory.is_dir():
            try:
                rmtree(directory)
            except OSError:
                res = res and False
    return res


def assertAccessibleFile(testcase: unittest.TestCase, file: Path, not_empty: bool = False) -> None:
    if not file.is_file():
        testcase.fail(f"{file} is not a file")
    with file.open("r") as f:
        if not f.readable():
            testcase.fail(f"{file} is not readable")
    with file.open("a") as f:
        if not f.writable():
            testcase.fail(f"{file} is not writable")
    if not_empty and file.stat().st_size == 0:
        testcase.fail(f"{file} is empty")


def assertFilesEqual(testcase: unittest.TestCase, test: Path, validation: Path) -> None:
    with test.open('r') as test_file:
        with validation.open('r') as validation_file:
            for idx, (test_line, validation_line) in \
                    enumerate(zip(test_file.readlines(), validation_file.readlines())):
                with testcase.subTest(test_file=test, validation_file=validation, line=idx):
                    if test_line.startswith("Creating") and validation_line.startswith("Creating"):
                        prefix_test, path_test = test_line.split(": ", 1)
                        prefix_validation, path_validation = validation_line.split(": ", 1)
                        _, path_test = path_test.split("recipe2txt", 1)
                        _, path_validation = path_validation.split("recipe2txt", 1)

                        test_line = prefix_test + ": " + path_test
                        validation_line = prefix_validation + ": " + path_validation

                    testcase.assertEqual(test_line, validation_line)


def assertEval(testcase: unittest.TestCase, func: Callable[..., Any],
               data: list[tuple[tuple[Any, ...] | Any, tuple[Any, ...] | Any]]) -> None:
    for idx, (test, validation) in enumerate(data):
        with testcase.subTest(iteration=idx, test_data=test, validation_data=validation):
            testcase.assertEqual(func(test), validation)




