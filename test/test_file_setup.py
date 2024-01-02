# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
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
import os.path
import unittest
from shutil import rmtree
from test.test_helpers import TEST_PROJECT_TMPDIR, TESTFILE, assertAccessibleFile

import recipe2txt.file_setup as fs
from recipe2txt.utils.ContextLogger import disable_loggers
from recipe2txt.utils.misc import (
    ensure_accessible_file_critical,
    ensure_existence_dir,
    is_accessible_db,
)

copy_debug_dirs = fs.DEBUG_DIRS
tmp_data_dir = TEST_PROJECT_TMPDIR / "test-xdg-dirs"

COPY_RECIPES_NAME_TXT = fs.RECIPES_NAME_TXT

disable_loggers()

test_debug_dirs = fs.ProgramDirectories(
    tmp_data_dir / "data", tmp_data_dir / "config", tmp_data_dir / "state"
)

db_path = test_debug_dirs.data / fs.DB_NAME
log_path = test_debug_dirs.state / fs.LOG_NAME


def name_back():
    fs.DEBUG_DIRS = copy_debug_dirs
    fs.RECIPES_NAME_TXT = COPY_RECIPES_NAME_TXT


def remove_dir():
    if tmp_data_dir.is_dir():
        rmtree(tmp_data_dir)


unittest.addModuleCleanup(name_back)
unittest.addModuleCleanup(remove_dir)


class Test(unittest.TestCase):
    def setUp(self) -> None:
        fs.DEBUG_DIRS = test_debug_dirs
        fs.DEFAULT_OUTPUT_LOCATION_NAME = "NOTAFILE"
        fs.RECIPES_NAME_TXT = TESTFILE
        for directory in test_debug_dirs:
            if not ensure_existence_dir(directory):
                self.fail(f"Could not create {directory}")

    def tearDown(self) -> None:
        name_back()
        remove_dir()

    def test_get_db(self):
        validation_path = test_debug_dirs.data / fs.DB_NAME

        db = fs.get_db(True)

        self.assertTrue(is_accessible_db(db))
        self.assertTrue(os.path.samefile(db, validation_path))

    def test_get_log(self):
        validation_path = test_debug_dirs.state / fs.LOG_NAME

        log = fs.get_log(True)

        assertAccessibleFile(self, log)
        self.assertTrue(os.path.samefile(log, validation_path))

        # Testing if existing files do not get overwritten:
        log.write_text("TEST")

        log = fs.get_log(True)
        self.assertEqual(log.read_text(), "TEST")

    def test_get_files(self):
        file1 = fs.DEBUG_DIRS.config / "file1"
        file2 = fs.DEBUG_DIRS.data / "file2"
        file3 = fs.DEBUG_DIRS.data / "file3"

        file1.write_text("TESTFILE")
        file2.write_text("TESTFILE")

        ensure_accessible_file_critical(file3)
        fs.get_db(True)
        fs.get_log(True)

        test_files = set(fs.get_files(True))
        tmp = [file1, file2, file3, db_path, log_path]
        validation_files = {str(file) for file in tmp}

        if diff1 := test_files - validation_files:
            self.fail(f"Files in test_files but not in validation_files: {diff1}")

        if diff2 := validation_files - test_files:
            self.fail(f"Files in validation_files but not in test_files: {diff2}")

    def test_erase_files(self):
        for directory in fs.DEBUG_DIRS:
            self.assertTrue(directory.is_dir())

        files = [
            directory / f"file-{idx}" for idx, directory in enumerate(fs.DEBUG_DIRS)
        ]
        for file in files:
            file.write_text("TESTFILE")
            assertAccessibleFile(self, file, True)

        fs.erase_files(True)

        for file in files:
            self.assertFalse(file.is_file())
        for directory in fs.DEBUG_DIRS:
            self.assertFalse(directory.is_dir())
