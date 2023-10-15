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
import shutil
import unittest
from pathlib import Path

import recipe2txt.utils.misc as misc
from test.test_helpers import *
from test.test_helpers import testfile, none_dirs, normal_dirs


class FileTests(unittest.TestCase):

    def setUp(self) -> None:
        if not create_tmpdirs():
            self.fail()

    def tearDown(self) -> None:
        if not delete_tmpdirs():
            self.fail()

    def test_extract_urls(self):
        obscured_urls = test_filedir / "permanent" / "obscured_urls.txt"
        unobscured_urls = obscured_urls.with_name("unobscured_urls.txt")
        if not obscured_urls.is_file():
            self.fail(f"{obscured_urls} does not exist.")
        if not unobscured_urls.is_file():
            self.fail(f"{unobscured_urls} does not exist.")

        validation = set()
        for url in misc.read_files(unobscured_urls):
            if url := url.strip():
                validation.add(url)

        lines = misc.read_files(obscured_urls)
        urls = misc.extract_urls(lines)
        if diff := validation-urls:
            self.fail(f"Validation contains URLs that were not extracted:{diff}")
        if diff := urls-validation:
            self.fail(f"Validation does not contain URLs that were extracted:{diff}")

    def test_full_path(self):
        params = [
            (["~", "Documents", "File1"], os.path.expanduser(os.path.join("~", "Documents", "File1"))),
            (["  /tmp", "dir1", "file2.txt  "], os.path.join("/tmp", "dir1", "file2.txt")),
            ([".", "file"], os.path.join(os.getcwd(), "file")),
            (["$HOME", "Documents", "File1"], os.path.expandvars(os.path.join("$HOME", "Documents", "File1"))),
            ([Path.cwd(), "NewDir", "File1.txt"], os.path.join(os.getcwd(), "NewDir", "File1.txt")),
            (["/home", "user", Path("Documents", "important"), "file1.txt"],
             os.path.join("/home", "user", "Documents", "important", "file1.txt"))
        ]

        for test, validation in params:
            with self.subTest(testdata=test):
                self.assertEqual(str(misc.full_path(*test)), validation)

    def test_ensure_existence_dir(self):
        params_path = [(test, os.path.join(*test)) for test in normal_dirs]

        for test, validation in params_path:
            with self.subTest(testpath=test):
                self.assertTrue(os.path.samefile(misc.ensure_existence_dir(*test), validation))
                os.removedirs(validation)

        for test in none_dirs:
            with self.subTest(directory=test):
                self.assertIsNone(misc.ensure_existence_dir(*test))

    def test_ensure_accessible_file(self):
        params_path = [(test, os.path.join(*test, testfile)) for test in normal_dirs]
        for test, validation in params_path:
            with self.subTest(directory=test):
                self.assertTrue(os.path.samefile(misc.ensure_accessible_file(*test, testfile), validation))
                if not os.path.isfile(validation):
                    self.fail("File", validation, "was not created")
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

        for test in none_dirs:
            self.assertIsNone(misc.ensure_accessible_file(*test, testfile))

    def test_ensure_critical(self):
        crit_fail_path = none_dirs[1]

        with self.assertRaises(SystemExit) as e:
            misc.ensure_existence_dir_critical(*crit_fail_path)
        self.assertEqual(e.exception.code, os.EX_IOERR)

        with self.assertRaises(SystemExit) as e:
            misc.ensure_accessible_file_critical(*crit_fail_path, testfile)
        self.assertEqual(e.exception.code, os.EX_IOERR)

    def test_read_files(self):
        file1_content = ["one", "two", "three", "four"]
        file2_content = ["five", "six", "seven", "eight"]

        file1_path = test_project_tmpdir / "testfile1.txt"
        file2_path = xdg_tmpdir / "testfile2.txt"
        file_notafile_path = test_project_tmpdir / "NOTAFILE"

        file1_path.write_text(os.linesep.join(file1_content) + os.linesep)
        file2_path.write_text(os.linesep.join(file2_content) + os.linesep)

        str_list = misc.read_files(file1_path, file_notafile_path, file2_path)

        for test, validation in zip(str_list, (file1_content + file2_content)):
            with self.subTest(validation_line=validation):
                self.assertEqual(test.rstrip(), validation)

        os.remove(file1_path)
        os.remove(file2_path)

    def test_dir_file_name_conflict(self):
        directory = misc.full_path(*normal_dirs[0])
        os.makedirs(directory, exist_ok=True)

        self.assertIsNone(misc.ensure_accessible_file(directory))
        shutil.rmtree(directory)
        assertAccessibleFile(self, misc.ensure_accessible_file(directory))

        self.assertIsNone(misc.ensure_existence_dir(directory))
        os.remove(directory)
        self.assertTrue(misc.ensure_existence_dir(directory).is_dir())


class StrTests(unittest.TestCase):

    def test_dict2str(self):
        dicts = [({1: "one", 2: "two", 3: "three"}, os.linesep.join(["1: one", "2: two", "3: three"])),
                 ({"one": "Eins", "two": "Zwei", "three": "Drei"},
                  os.linesep.join(["one: Eins", "two: Zwei", "three: Drei"]))]

        for d, validation in dicts:
            with self.subTest(testdict=d):
                self.assertEqual(misc.dict2str(d), validation)

    def test_head_str(self):
        objects = [("teststringteststringteststring", "teststr..."),
                   ("teststring", "teststring"),
                   ("test       ", "test..."),
                   ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "[1, 2,...")]

        for obj, validation in objects:
            with self.subTest(testobj=obj):
                self.assertEqual(misc.head_str(obj, 10), validation)
