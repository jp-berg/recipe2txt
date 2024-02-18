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
# recipe2txt. If not, see <https://www.gnu.org/licenses/

import unittest
from test.test_helpers import TEST_PROJECT_TMPDIR, TESTFILE, delete_tmpdirs
from test.testfiles.permanent.testfile_generator import (
    FULL_MD,
    FULL_TXT,
    MD_LIST,
    RECIPE_LIST,
    TXT_LIST,
)

from recipe2txt.recipes2out import RecipeWriter
from recipe2txt.utils.ContextLogger import suppress_logging
from recipe2txt.utils.filesystem import ensure_accessible_file_critical

TESTFILE_MD = TESTFILE.replace("txt", "md")


class Test(unittest.TestCase):

    def tearDown(self) -> None:
        delete_tmpdirs()

    def test_RecipeWriter_single_recipe_txt(self):

        for recipe, validation_recipe in zip(RECIPE_LIST, TXT_LIST):
            with self.subTest(recipe=recipe.title):
                file = ensure_accessible_file_critical(TEST_PROJECT_TMPDIR, TESTFILE)
                with suppress_logging():
                    txt_writer = RecipeWriter(file, "txt", True)
                    txt_writer.write([recipe])

                test_recipe = file.read_text()
                self.assertEqual(test_recipe, validation_recipe)

                delete_tmpdirs()

    def test_RecipeWriter_multiple_recipes_txt(self):
        file = ensure_accessible_file_critical(TEST_PROJECT_TMPDIR, TESTFILE)
        with suppress_logging():
            txt_writer = RecipeWriter(file, "txt", True)
            txt_writer.write(RECIPE_LIST)

        test_recipes = file.read_text()
        self.assertEqual(test_recipes, FULL_TXT)

    def test_RecipeWriter_single_recipe_md(self):

        for recipe, validation_recipe in zip(RECIPE_LIST, MD_LIST):
            with self.subTest(recipe=recipe.title):
                file = ensure_accessible_file_critical(TEST_PROJECT_TMPDIR, TESTFILE_MD)
                with suppress_logging():
                    txt_writer = RecipeWriter(file, "md", True)
                    txt_writer.write([recipe])

                test_recipe = file.read_text()
                self.assertEqual(test_recipe, validation_recipe)

                delete_tmpdirs()

    def test_RecipeWriter_multiple_recipes_md(self):
        file = ensure_accessible_file_critical(TEST_PROJECT_TMPDIR, TESTFILE_MD)
        with suppress_logging():
            txt_writer = RecipeWriter(file, "md", True)
            txt_writer.write(RECIPE_LIST)

        test_recipes = file.read_text()
        self.assertEqual(test_recipes, FULL_MD)
