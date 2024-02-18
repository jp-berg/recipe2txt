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
import os
import shutil
import unittest
from pathlib import Path
from test.test_helpers import (
    NONE_DIRS,
    NORMAL_DIRS,
    TEST_PROJECT_TMPDIR,
    TESTFILE,
    XDG_TMPDIR,
    assertAccessibleFile,
    create_tmpdirs,
    delete_tmpdirs,
)
from test.test_sql import db_name, db_paths

from recipe2txt.utils import filesystem


class FileTests(unittest.TestCase):
    def setUp(self) -> None:
        if not create_tmpdirs():
            self.fail()

    def tearDown(self) -> None:
        if not delete_tmpdirs():
            self.fail()

    def test_is_accessible_db(self):
        for path in db_paths:
            with self.subTest(path=path):
                self.assertTrue(filesystem.is_accessible_db(path))

        db_path_inaccessible = os.path.join("/root", db_name)
        self.assertFalse(filesystem.is_accessible_db(db_path_inaccessible))

        db_path_nonexistent = os.path.join(TEST_PROJECT_TMPDIR, "NOT_A_FOLDER", db_name)
        self.assertFalse(filesystem.is_accessible_db(db_path_nonexistent))

    def test_full_path(self):
        params = [
            (
                ["~", "Documents", "File1"],
                os.path.expanduser(os.path.join("~", "Documents", "File1")),
            ),
            (
                ["  /tmp", "dir1", "file2.txt  "],
                os.path.join("/tmp", "dir1", "file2.txt"),
            ),
            ([".", "file"], os.path.join(os.getcwd(), "file")),
            (
                ["$HOME", "Documents", "File1"],
                os.path.expandvars(os.path.join("$HOME", "Documents", "File1")),
            ),
            (
                [Path.cwd(), "NewDir", "File1.txt"],
                os.path.join(os.getcwd(), "NewDir", "File1.txt"),
            ),
            (
                ["/home", "user", Path("Documents", "important"), "file1.txt"],
                os.path.join("/home", "user", "Documents", "important", "file1.txt"),
            ),
        ]

        for test, validation in params:
            with self.subTest(testdata=test):
                self.assertEqual(str(filesystem.full_path(*test)), validation)

    def test_ensure_existence_dir(self):
        params_path = [(test, os.path.join(*test)) for test in NORMAL_DIRS]

        for test, validation in params_path:
            with self.subTest(testpath=test):
                self.assertTrue(
                    os.path.samefile(
                        filesystem.ensure_existence_dir(*test),
                        validation,
                    )
                )
                os.removedirs(validation)

        for test in NONE_DIRS:
            with self.subTest(directory=test):
                self.assertIsNone(filesystem.ensure_existence_dir(*test))

    def test_ensure_accessible_file(self):
        params_path = [(test, os.path.join(*test, TESTFILE)) for test in NORMAL_DIRS]
        for test, validation in params_path:
            with self.subTest(directory=test):
                self.assertTrue(
                    os.path.samefile(
                        filesystem.ensure_accessible_file(*test, TESTFILE),
                        validation,
                    )
                )
                if not os.path.isfile(validation):
                    self.fail(f"File {validation} was not created")
                try:
                    with open(validation, "w") as file:
                        file.write("TEST")
                    with open(validation, "r") as file:
                        content = file.readline().rstrip(os.linesep)
                        self.assertEqual(content, "TEST")
                except OSError as e:
                    self.fail(e)

                os.remove(validation)
                os.rmdir(validation := os.path.dirname(validation))
                os.rmdir(os.path.dirname(validation))

        for test in NONE_DIRS:
            self.assertIsNone(filesystem.ensure_accessible_file(*test, TESTFILE))

    def test_ensure_critical(self):
        crit_fail_path = NONE_DIRS[1]

        with self.assertRaises(SystemExit) as e:
            filesystem.ensure_existence_dir_critical(*crit_fail_path)
        self.assertEqual(e.exception.code, os.EX_IOERR)

        with self.assertRaises(SystemExit) as e:
            filesystem.ensure_accessible_file_critical(*crit_fail_path, TESTFILE)
        self.assertEqual(e.exception.code, os.EX_IOERR)

    def test_read_files(self):
        file1_content = ["one", "two", "three", "four"]
        file2_content = ["five", "six", "seven", "eight"]

        file1_path = TEST_PROJECT_TMPDIR / "testfile1.txt"
        file2_path = XDG_TMPDIR / "testfile2.txt"
        file_notafile_path = TEST_PROJECT_TMPDIR / "NOTAFILE"

        file1_path.write_text(os.linesep.join(file1_content) + os.linesep)
        file2_path.write_text(os.linesep.join(file2_content) + os.linesep)

        str_list = filesystem.read_files(file1_path, file_notafile_path, file2_path)

        for test, validation in zip(str_list, (file1_content + file2_content)):
            with self.subTest(validation_line=validation):
                self.assertEqual(test.rstrip(), validation)

        os.remove(file1_path)
        os.remove(file2_path)

    def test_dir_file_name_conflict(self):
        directory = filesystem.full_path(*NORMAL_DIRS[0])
        os.makedirs(directory, exist_ok=True)

        self.assertIsNone(filesystem.ensure_accessible_file(directory))
        shutil.rmtree(directory)
        assertAccessibleFile(self, filesystem.ensure_accessible_file(directory))

        self.assertIsNone(filesystem.ensure_existence_dir(directory))
        os.remove(directory)
        self.assertTrue(filesystem.ensure_existence_dir(directory).is_dir())
