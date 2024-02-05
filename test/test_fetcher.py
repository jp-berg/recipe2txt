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

import random
import test.testfiles.permanent.testfile_generator as file_gen
import unittest
from test.test_helpers import TEST_PROJECT_TMPDIR, create_tmpdirs, delete_tmpdirs
from test.test_sql import db_path, out_name_md, out_name_txt, out_path_txt
from typing import Final

from recipe2txt.fetcher import Cache, Fetcher
from recipe2txt.sql import Database
from recipe2txt.utils.misc import URL, ensure_accessible_file, is_accessible_db


class TestFileFetcher(Fetcher):
    URL2HTML: Final[dict[str, bytes]] = {
        url: html for url, html in zip(file_gen.URL_LIST, file_gen.HTML_LIST)
    }

    def fetch(self, urls: set[URL]) -> None:
        urls = super().require_fetching(urls)
        for url in urls:
            html = TestFileFetcher.URL2HTML[url]
            self.html2db(url, html)  # type: ignore[arg-type]


class Test(unittest.TestCase):
    def setUp(self) -> None:
        create_tmpdirs()
        if not is_accessible_db(db_path):
            self.fail(f"Could not create tmp database: {db_path}")
        if not ensure_accessible_file(TEST_PROJECT_TMPDIR, out_name_txt):
            self.fail(f"Could not create/access tmp file: {out_path_txt}")
        if not ensure_accessible_file(TEST_PROJECT_TMPDIR, out_name_md):
            self.fail(f"Could not create/access tmp file: {out_path_txt}")

    def tearDown(self) -> None:
        delete_tmpdirs()

    def test_require_fetching(self):
        tf = TestFileFetcher(database=Database(db_path, out_path_txt))

        urls = file_gen.URL_LIST
        random.shuffle(urls)
        first = set(file_gen.URL_LIST[:2])
        tf.fetch(first)

        err_msg = "require_fetching() does not filter adequately with setting %s"

        tf.cache = Cache.DEFAULT
        to_fetch = tf.require_fetching(urls)

        if to_fetch == urls[2:]:
            self.fail(err_msg % f"{tf.cache=} | Got {to_fetch}, expected {urls[:2]} ")

        tf.cache = Cache.ONLY
        to_fetch = tf.require_fetching(urls)
        if to_fetch:
            self.fail(err_msg % f"{tf.cache=} | Got {to_fetch}, expected empty set")

        tf.cache = Cache.NEW
        to_fetch = tf.require_fetching(urls)
        if len(urls) != len(to_fetch):
            self.fail(err_msg % f"{tf.cache=} | Got {to_fetch}, expected {urls}")
