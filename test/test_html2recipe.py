import unittest
import recipe_scrapers
import recipe2txt.html2recipe as h2r
import test.testfiles.html2recipe.testfile_generator as file_gen
from .test_helpers import *
import os


class Test(unittest.TestCase):

    def test_none2na(self):
        wrong_length = (1,) * (len(h2r.recipe_attributes) + 1)
        with self.assertRaises(ValueError):
            h2r.none2na(wrong_length)

        test_tuple = [((1, 2, 3, None, 5, 6), (1, 2, 3, h2r.NA, 5, 6)),
                      ((None, 2, None, 4, None, 6, 7), (h2r.NA, 2, h2r.NA, 4, h2r.NA, 6, 7))]

        for t, v in test_tuple:
            with self.subTest(i=t):
                self.assertEqual(h2r.none2na(t), v)

    def test_Recipe_attributes(self):
        r = h2r.Recipe()
        for a in h2r.recipe_attributes:
            with self.subTest(i=a):
                self.assertTrue(hasattr(r, a))

        r = h2r.Recipe(*h2r.recipe_attributes)
        for a in h2r.recipe_attributes:
            with self.subTest(i=a):
                self.assertEqual(getattr(r, a), a)

    def test_int2status(self):
        recipes = [recipe[:-2] + (int(recipe[-2]), recipe[-1]) for recipe in test_recipes]
        for recipe, validation in zip(recipes, test_recipes):
            with self.subTest(i=recipe[-3]):
                self.assertEqual(h2r.int2status(recipe), validation)

    def test__get_info(self):
        for html, url, recipe in zip(file_gen.html, file_gen.urls, file_gen.recipes):
            p = recipe_scrapers.scrape_html(html=html, org_url=url)
            for method in h2r.methods:
                with self.subTest(i=url + " | " + method):
                    self.assertEqual(h2r._get_info(method, p, h2r.nocontext), getattr(recipe, method))

    def test_html2recipe(self):
        for url, html, validation in zip(file_gen.urls, file_gen.html, file_gen.recipes):
            with self.subTest(i=url):
                if not (p := h2r.html2parsed(url, html)):
                    self.fail("Failed to parse")
                if not (recipe := h2r.parsed2recipe(url, p)):
                    self.fail("Failed to convert to recipe")
                for a in h2r.recipe_attributes[:-1]: # scraper version will probably differ
                    with self.subTest(i=a):
                        r = getattr(recipe, a)
                        v = getattr(validation, a)
                        self.assertEqual(v, r)

        self.assertIsNone(h2r.html2parsed(*file_gen.html_bad))

    def test_gen_status(self):
        for recipe in test_recipes[2:]:
            with self.subTest(i=recipe.url):
                status = recipe.status
                self.assertEqual(h2r.gen_status(list(recipe[:len(h2r.methods)])), status)

        with self.assertRaises(ValueError):
            h2r.gen_status(list(h2r.Recipe()))

    def test_recipe2out(self):
        for recipe, md, txt in zip(file_gen.recipes, file_gen.md, file_gen.txt):
            with self.subTest(i=recipe.url +"| txt"):
                out_txt = h2r.recipe2out(recipe, counts=None, md=False)
                self.assertEqual(out_txt, txt)
            with self.subTest(i=recipe.url + "| md"):
                out_md = h2r.recipe2out(recipe, counts=None, md=True)
                self.assertEqual(out_md, md)

    @unittest.skip("Seems not verifiable in current form")
    def test_html2parsed(self):
        for html, url in zip(file_gen.html, file_gen.urls):
            with self.subTest(i=os.path.basename(url)):
                self.assertEqual(h2r.html2parsed(url, html), recipe_scrapers.scrape_html(html=html, org_url=url))