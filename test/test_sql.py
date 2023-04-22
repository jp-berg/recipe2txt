import sqlite3
import sys
import unittest
import os
import recipe2txt.html2recipe as h2r
import recipe2txt.sql as sql
import recipe2txt.utils.misc as misc
from .test_helpers import *
from typing import Optional

db_name = "db_test.sqlite3"

db_path = os.path.join(test_project_tmpdir, db_name)
db_paths = [os.path.join(folder, db_name) for folder in tmpdirs]
out_path = os.path.join(test_project_tmpdir, "out_test.txt")

db: sql.Database




def compare_for(recipe1: h2r.Recipe, recipe2: h2r.Recipe, *attributes: str, equality: bool = True) -> Optional[str]:
    for attr in attributes:
        if attr not in h2r.recipe_attributes:
            raise ValueError("Not a valid attribute for Recipe: " + attr)
        val1 = str(getattr(recipe1, attr))
        val2 = str(getattr(recipe2, attr))
        if equality:
            if val1 != val2:
                return " ".join([attr, ":", str(val1), " | ", str(val2)])
        else:
            if val1 == val2:
                return " ".join([attr, ":", str(val1), " | ", str(val2)])
    return None


class TestHelpers(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not create_tmpdirs():
            print("Could not create tmpdirs:", tmpdirs, file=sys.stderr)

    @classmethod
    def tearDownClass(cls) -> None:
        if not delete_tmpdirs():
            print("Could not delete tmpdirs:", tmpdirs, file=sys.stderr)

    def test_fetch_again(self):
        truth_up_to_date = [True, True, False, True, False, False, False]
        truth_out_of_date = [True, True, True, True, True, True, False]
        version_up_to_date = h2r.SCRAPER_VERSION
        version_out_of_date = '-1'

        self.assertEqual(len(truth_up_to_date), len(h2r.RecipeStatus))
        self.assertEqual(len(truth_out_of_date), len(h2r.RecipeStatus))

        for status, up_to_date, out_of_date in zip(h2r.RecipeStatus, truth_up_to_date, truth_out_of_date):
            with self.subTest(i=status):
                self.assertEqual(sql.fetch_again(status, version_up_to_date), up_to_date)
                self.assertEqual(sql.fetch_again(status, version_out_of_date), out_of_date)

    def test_is_accessible_db(self):
        for path in db_paths:
            with self.subTest(i=path):
                self.assertTrue(sql.is_accessible_db(path))

        db_path_inaccessible = os.path.join("/root", db_name)
        self.assertFalse(sql.is_accessible_db(db_path_inaccessible))

        db_path_nonexistent = os.path.join(test_project_tmpdir, "NOT_A_FOLDER", db_name)
        self.assertFalse(sql.is_accessible_db(db_path_nonexistent))


class TestDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not create_tmpdirs():
            print("Could not create tmpdirs:", tmpdirs, file=sys.stderr)


    @classmethod
    def tearDownClass(cls) -> None:
        if not delete_tmpdirs():
            print("Could not delete tmpdirs:", tmpdirs, file=sys.stderr)

    def setUp(self) -> None:
        misc.set_vlevel(0)
        if sql.is_accessible_db(db_path):
            global db
            db = sql.Database(db_path, misc.File(out_path))
            for recipe in test_recipes:
                with self.subTest(i=recipe.url):
                    try:
                        db.new_recipe(recipe)
                    except sqlite3.OperationalError:
                        self.fail("ERROR")
        else:
            self.fail("Database " + db_path + " not accessible")

    def tearDown(self) -> None:
        db.empty_db()


    def test_basic_IO(self):
        for recipe in test_recipes:
            with self.subTest(i=recipe.status):
                from_db = db.get_recipe(recipe.url)
                self.assertEqual(recipe, from_db)

    def test_get_titles(self):
        titles, hosts = zip(*db.get_titles())
        self.assertEqual(len(titles), len(test_recipes[3:]))
        for recipe, title, host in zip(test_recipes[3:], titles, hosts):
            with self.subTest(i=recipe.url):
                self.assertEqual(recipe.title, title)
                self.assertEqual(recipe.host, host)

    def test_urls_to_fetch(self):
        urls = set([recipe.url for recipe in test_recipes])
        to_fetch = db.urls_to_fetch(urls)
        for recipe in test_recipes:
            with self.subTest(i=recipe.url):
                if recipe.status in (h2r.RecipeStatus.NOT_INITIALIZED,
                                     h2r.RecipeStatus.UNREACHABLE,
                                     h2r.RecipeStatus.INCOMPLETE_ESSENTIAL):
                    self.assertTrue(recipe.url in to_fetch)
                else:
                    self.assertFalse(recipe.url in to_fetch)
                    if recipe.status in (h2r.RecipeStatus.UNKNOWN,
                                         h2r.RecipeStatus.INCOMPLETE_ON_DISPLAY,
                                         h2r.RecipeStatus.COMPLETE_ON_DISPLAY):
                        self.assertTrue(sql.fetch_again(recipe.status, '0.0'))

    def test_insert_recipe(self):
        updated = h2r.Recipe(
            title=test_recipes[2].title, url=test_recipes[2].url,
            status=h2r.RecipeStatus.INCOMPLETE_ON_DISPLAY,
            ingredients=os.linesep.join(["Something starchy", "Some spices", "Something crunchy"]),
            instructions=os.linesep.join(["Dice", "Mix", "Fry", "Eat"]), total_time="30"
        )

        on_disk = db.get_recipe(updated.url)
        if failed := compare_for(on_disk, updated, "status", "ingredients", "instructions", "total_time",
                                 equality=False):
            self.fail("Recipe comparison (inequality) failed on attribute " + failed)

        tmp = db.insert_recipe(updated)
        on_disk = db.get_recipe(updated.url)
        self.assertIsNotNone(on_disk)
        self.assertEqual(tmp, on_disk)

        if failed := compare_for(on_disk, updated, "title", "url", "status", "ingredients", "instructions",
                                 "total_time"):
            self.fail("Recipe comparison (equality) failed on attribute " + failed)

        self.assertNotEqual(updated.host, on_disk.host)
        self.assertEqual(test_recipes[2].host, on_disk.host)

    def test_get_contents(self):
        global db
        db.close()
        out_path2 = os.path.join(test_project_tmpdir, "out_test2.txt")
        db = sql.Database(db_path, out_path2)

        testrecipe = h2r.Recipe(url="https://www.testurl.com/testrecipe", scraper_version=h2r.SCRAPER_VERSION,
                                title="Testrecipe", host="testurl.com", ingredients=os.linesep.join(["ham", "spam"]),
                                instructions=os.linesep.join(
                                    ["Clean data", "Classify data", "Label data", "train model"]),
                                total_time='120', yields='1', status=h2r.RecipeStatus.COMPLETE_ON_DISPLAY)
        db.new_recipe(testrecipe)
        db.close()

        db = sql.Database(db_path, out_path)
        contents = db.get_contents()
        self.assertEqual(len(contents), len(test_recipes))
        for recipe in test_recipes:
            with self.subTest(i=recipe.url):
                self.assertTrue(recipe.url in contents)
        db.close()

        db = sql.Database(db_path, out_path2)
        contents = db.get_contents()
        self.assertEqual(len(contents), 1)
        self.assertEqual(testrecipe.url, contents[0])

    def test_empty_db(self):
        recipes = db.get_recipes()

        for recipe, validation in zip(recipes, test_recipes[3:]):
            with self.subTest(i=recipe.url):
                self.assertEqual(recipe, validation)

        db.empty_db()
        with self.assertRaises(sqlite3.OperationalError):
            db.get_recipes()