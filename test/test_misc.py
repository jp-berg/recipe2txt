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
import unittest
from test.test_helpers import TEST_FILEDIR, create_tmpdirs, delete_tmpdirs

from recipe2txt.utils import misc
from recipe2txt.utils.filesystem import read_files


class TestExtractUrls(unittest.TestCase):
    def setUp(self) -> None:
        if not create_tmpdirs():
            self.fail()

    def tearDown(self) -> None:
        if not delete_tmpdirs():
            self.fail()

    def test_extract_urls(self):
        obscured_urls = TEST_FILEDIR / "permanent" / "obscured_urls.txt"
        unobscured_urls = obscured_urls.with_name("unobscured_urls.txt")
        if not obscured_urls.is_file():
            self.fail(f"{obscured_urls} does not exist.")
        if not unobscured_urls.is_file():
            self.fail(f"{unobscured_urls} does not exist.")

        validation = set()
        for url in read_files(unobscured_urls):
            if url := url.strip():
                validation.add(url)

        lines = read_files(obscured_urls)
        urls = misc.extract_urls(lines)
        if diff := validation - urls:
            self.fail(f"Validation contains URLs that were not extracted:{diff}")
        if diff := urls - validation:
            self.fail(f"Validation does not contain URLs that were extracted:{diff}")


class StrTests(unittest.TestCase):
    def test_dict2str(self):
        dicts = [
            (
                {1: "one", 2: "two", 3: "three"},
                os.linesep.join(["1: one", "2: two", "3: three"]),
            ),
            (
                {"one": "Eins", "two": "Zwei", "three": "Drei"},
                os.linesep.join(["one: Eins", "two: Zwei", "three: Drei"]),
            ),
        ]

        for d, validation in dicts:
            with self.subTest(testdict=d):
                self.assertEqual(misc.dict2str(d), validation)

    def test_head_str(self):
        objects = [
            ("teststringteststringteststring", "teststr..."),
            ("teststring", "teststring"),
            ("test       ", "test..."),
            ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "[1, 2,..."),
        ]

        for obj, validation in objects:
            with self.subTest(testobj=obj):
                self.assertEqual(misc.head_str(obj, 10), validation)
