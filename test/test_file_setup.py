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

import os
import unittest
from pathlib import Path
from shutil import rmtree

from recipe2txt.sql import is_accessible_db
from recipe2txt.utils.ContextLogger import disable_loggers
from test.test_helpers import test_project_tmpdir, assertAccessibleFile
from test.test_misc import testfile
import recipe2txt.file_setup as fs
from recipe2txt.utils.misc import ensure_existence_dir, full_path

copy_debug_dirs = fs.debug_dirs
tmp_data_dir = test_project_tmpdir / "test-xdg-dirs"

COPY_DEFAULT_OUTPUT_LOCATION_NAME = fs.DEFAULT_OUTPUT_LOCATION_NAME
COPY_RECIPES_NAME_TXT = fs.RECIPES_NAME_TXT

disable_loggers()


test_debug_dirs = fs.ProgramDirectories(tmp_data_dir / "data",
                                        tmp_data_dir / "config",
                                        tmp_data_dir / "state")

def name_back():
    fs.debug_dirs = copy_debug_dirs
    fs.DEFAULT_OUTPUT_LOCATION_NAME = COPY_DEFAULT_OUTPUT_LOCATION_NAME
    fs.RECIPES_NAME_TXT = COPY_RECIPES_NAME_TXT


def remove_dir():
    if tmp_data_dir.is_dir():
        rmtree(tmp_data_dir)


unittest.addModuleCleanup(name_back)
unittest.addModuleCleanup(remove_dir)


class Test(unittest.TestCase):

    def setUp(self) -> None:
        fs.debug_dirs = test_debug_dirs
        fs.DEFAULT_OUTPUT_LOCATION_NAME = "NOTAFILE"
        fs.RECIPES_NAME_TXT = testfile
        for directory in test_debug_dirs:
            if not ensure_existence_dir(directory):
                self.fail(f"Could not create {directory}")

    def tearDown(self) -> None:
        name_back()
        remove_dir()

    def test_file_setup(self):
        db_path = test_debug_dirs.data / fs.DB_NAME
        log_path = test_debug_dirs.state / fs.LOG_NAME
        testfile_txt = test_project_tmpdir / testfile
        params = [((True,),
                   (db_path, Path.cwd() / fs.RECIPES_NAME_TXT, log_path)),
                  ((True, str(testfile_txt), False),
                   (db_path, testfile_txt, log_path)),
                  ((True, str(testfile_txt.with_suffix(".md")), True),
                   (db_path, testfile_txt.with_suffix(".md"), log_path))
                  ]

        for idx, (test, validation) in enumerate(params):
            fs.file_setup(*test)
            with self.subTest(i=idx):
                is_accessible_db(validation[0])
                assertAccessibleFile(self, validation[1])
                assertAccessibleFile(self, validation[2])

        os.remove(Path.cwd() / fs.RECIPES_NAME_TXT)

    def test_get_files(self):
        file1 = fs.debug_dirs.config / "file1"
        file2 = fs.debug_dirs.data / "file2"
        file3 = fs.debug_dirs.data / "file3"

        file1.write_text("TESTFILE")
        file2.write_text("TESTFILE")

        db_path = fs.debug_dirs.data / fs.DB_NAME
        log_path = fs.debug_dirs.state / fs.LOG_NAME
        fs.file_setup(True, file3)

        test_files = set(fs.get_files(True))
        tmp = [file1, file2, file3, db_path, log_path]
        validation_files = {str(file) for file in tmp}

        if diff1 := test_files - validation_files:
            self.fail(f"Files in test_files but not in validation_files: {diff1}")

        if diff2 := validation_files - test_files:
            self.fail(f"Files in validation_files but not in test_files: {diff2}")

    def test_erase_files(self):
        for directory in fs.debug_dirs:
            self.assertTrue(directory.is_dir())

        files = [directory / f"file-{idx}" for idx, directory in enumerate(fs.debug_dirs)]
        for file in files:
            file.write_text("TESTFILE")
            assertAccessibleFile(self, file, True)

        fs.erase_files(True)

        for file in files:
            self.assertFalse(file.is_file())
        for directory in fs.debug_dirs:
            self.assertFalse(directory.is_dir())

    def test_default_output(self):
        testpath = str(full_path(test_project_tmpdir / "out"))
        default_output = fs.debug_dirs.config / fs.DEFAULT_OUTPUT_LOCATION_NAME

        self.assertFalse(default_output.is_file())
        fs.set_default_output(testpath, True)
        self.assertTrue(default_output.is_file())

        content = default_output.read_text().split(os.linesep)
        self.assertEqual(content[0], testpath + ".txt")
        self.assertEqual(content[1], testpath + ".md")

        output = fs.get_default_output(fs.debug_dirs.config, markdown=False)

        self.assertEqual(str(output), testpath + ".txt")
        assertAccessibleFile(self, output)

        with self.assertRaises(SystemExit) as ex:
            fs.set_default_output("/root/recipe", True)
            fs.get_default_output(fs.debug_dirs.config, markdown=False)
            self.assertEqual(ex.exception.code, os.EX_IOERR)

        fs.set_default_output("RESET", True)
        self.assertFalse(default_output.is_file())

        output = fs.get_default_output(fs.debug_dirs.config, markdown=False)

        default_recipe_file = Path.cwd() / fs.RECIPES_NAME_TXT
        assertAccessibleFile(self, default_recipe_file)
        self.assertEqual(output, default_recipe_file)

        os.remove(default_recipe_file)
