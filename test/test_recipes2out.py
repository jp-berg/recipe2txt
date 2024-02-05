import unittest
from test.test_helpers import TEST_PROJECT_TMPDIR, TESTFILE, delete_tmpdirs
from test.testfiles.permanent.testfile_generator import FULL_TXT, RECIPE_LIST, TXT_LIST

from recipe2txt.recipes2out import RecipeWriter
from recipe2txt.utils.ContextLogger import suppress_logging
from recipe2txt.utils.misc import ensure_accessible_file_critical

TESTFILE_TXT = TEST_PROJECT_TMPDIR / TESTFILE


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
