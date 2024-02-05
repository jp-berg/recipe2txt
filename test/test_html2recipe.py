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
import test.testfiles.permanent.testfile_generator as file_gen
import unittest
from test.test_helpers import test_recipes

import recipe_scrapers

import recipe2txt.html2recipe as h2r


class Test(unittest.TestCase):
    def test_none2na(self):
        wrong_length = (1,) * (len(h2r.RECIPE_ATTRIBUTES) + 1)
        with self.assertRaises(ValueError):
            h2r.none2na(wrong_length)

        test_tuple = [
            ((1, 2, 3, None, 5, 6), (1, 2, 3, h2r.NA, 5, 6)),
            ((None, 2, None, 4, None, 6, 7), (h2r.NA, 2, h2r.NA, 4, h2r.NA, 6, 7)),
        ]

        for t, v in test_tuple:
            with self.subTest(testdata=t):
                self.assertEqual(h2r.none2na(t), v)

    def test_Recipe_attributes(self):
        r = h2r.Recipe()
        for a in h2r.RECIPE_ATTRIBUTES:
            with self.subTest(attribute=a):
                self.assertTrue(hasattr(r, a))

        r = h2r.Recipe(*h2r.RECIPE_ATTRIBUTES)
        for a in h2r.RECIPE_ATTRIBUTES:
            with self.subTest(attribute=a):
                self.assertEqual(getattr(r, a), a)

    def test_int2status(self):
        recipes = [
            recipe[:-2] + (int(recipe[-2]), recipe[-1]) for recipe in test_recipes
        ]
        for recipe, validation in zip(recipes, test_recipes):
            with self.subTest(statuscode=recipe[-3]):
                self.assertEqual(h2r.int2status(recipe), validation)

    def test__get_info(self):
        for html, url, recipe in zip(
            file_gen.HTML_LIST, file_gen.URL_LIST, file_gen.RECIPE_LIST
        ):
            p = recipe_scrapers.scrape_html(html=html, org_url=url)
            for method in h2r.METHODS:
                with self.subTest(url=url, method=method):
                    self.assertEqual(h2r.get_info(method, p), getattr(recipe, method))

        bad_info = [
            ("total_time", 0),
            ("ingredients", None),
            ("ingredients", []),
            ("instructions", [None, None]),
            ("instructions", ["", "\t", "\n"]),
            ("ingredients", "{["),
            ("instructions", ["[", " ", "}"]),
        ]

        for url, (method, info) in zip(file_gen.URL_LIST, bad_info):
            with self.subTest(method=method, info=info):
                self.assertEqual(h2r.get_info(method, info), h2r.NA)

    def test_html2recipe(self):
        for url, html, validation in zip(
            file_gen.URL_LIST, file_gen.HTML_LIST, file_gen.RECIPE_LIST
        ):
            with self.subTest(url=url):
                if not (p := h2r.html2parsed(url, html)):
                    self.fail("Failed to parse")
                if not (recipe := h2r.parsed2recipe(p)):
                    self.fail("Failed to convert to recipe")
                for a in h2r.RECIPE_ATTRIBUTES[
                    :-1
                ]:  # scraper version will probably differ
                    with self.subTest(attribute=a):
                        r = getattr(recipe, a)
                        v = getattr(validation, a)
                        self.assertEqual(v, r)

        self.assertIsNone(h2r.html2parsed(*file_gen.HTML_BAD))

    def test_gen_status(self):
        for recipe in test_recipes[2:]:
            with self.subTest(recipe=recipe.url):
                status = recipe.status
                self.assertEqual(
                    h2r.gen_status(list(recipe[: len(h2r.METHODS)])), status
                )

        with self.assertRaises(ValueError):
            h2r.gen_status(list(h2r.Recipe()))

    @unittest.skip("Seems not verifiable in current form")
    def test_html2parsed(self):
        for html, url in zip(file_gen.HTML_LIST, file_gen.URL_LIST):
            with self.subTest(i=os.path.basename(url)):
                self.assertEqual(
                    h2r.html2parsed(url, html),
                    recipe_scrapers.scrape_html(html=html, org_url=url),
                )
