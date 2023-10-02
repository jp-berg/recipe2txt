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

import unittest

import recipe2txt.utils.ArgConfig as argconfig
from test.test_helpers import assertEval


class TestFunctions(unittest.TestCase):

    def test_short_flag(self):
        params = [("verbose", "-v"),
                  ("file", "-f"),
                  ("set-location", "-sl"),
                  ("no-overwrite-files", "-nof")]

        assertEval(self, argconfig.short_flag, params)

    def test_obj2toml(self):
        params = [(True, "true"),
                  ("test", "'test'"),
                  ([1, 2, 3], "[1, 2, 3]"),
                  (["one", "two", "three"], "['one', 'two', 'three']"),
                  ({"four": True, "five": False, "six": True},
                   "{'four': true, 'five': false, 'six': true}")]

        assertEval(self, argconfig.obj2toml, params)
