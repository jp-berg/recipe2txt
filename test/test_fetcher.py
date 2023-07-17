import random
import unittest
from recipe2txt.fetcher_abstract import Cache
from recipe2txt.utils.misc import ensure_existence_dir, ensure_accessible_file
from recipe2txt.sql import is_accessible_db
import test.testfiles.permanent.testfile_generator as file_gen
from test.test_helpers import *
from test.test_sql import db_path, out_path_txt, out_path_md, out_name_txt, out_name_md


class Test(unittest.TestCase):

    def setUp(self) -> None:
        create_tmpdirs()
        if not is_accessible_db(db_path):
            self.fail(f"Could not create tmp database: {db_path}")
        if not ensure_accessible_file(test_project_tmpdir, out_name_txt):
            self.fail(f"Could not create/access tmp file: {out_path_txt}")
        if not ensure_accessible_file(test_project_tmpdir, out_name_md):
            self.fail(f"Could not create/access tmp file: {out_path_txt}")

    def tearDown(self) -> None:
        delete_tmpdirs()

    def test_require_fetching(self):

        tf = file_gen.TestFileFetcher(output=out_path_txt,
                                      database=db_path)

        urls = file_gen.url_list
        random.shuffle(urls)
        first = set(file_gen.url_list[:2])
        tf.fetch(first)

        err_msg = "require_fetching() does not filter adequately with setting %s"

        tf.cache = Cache.default
        to_fetch = tf.require_fetching(urls)

        if to_fetch == urls[2:]:
            self.fail(err_msg % f"{tf.cache=} | Got {to_fetch}, expected {urls[:2]} ")

        tf.cache = Cache.only
        to_fetch = tf.require_fetching(urls)
        if to_fetch:
            self.fail(err_msg % f"{tf.cache=} | Got {to_fetch}, expected empty set")

        tf.cache = Cache.new
        to_fetch = tf.require_fetching(urls)
        if len(urls) != len(to_fetch):
            self.fail(err_msg % f"{tf.cache=} | Got {to_fetch}, expected {urls}")

    def test_write_txt(self):
        tf = file_gen.TestFileFetcher(output=out_path_txt,
                                      database=db_path, markdown=False)

        urls = file_gen.url_list
        tf.fetch(urls)
        with open(out_path_txt, "r") as file:
            for line, validation in zip(file, file_gen.full_txt):
                with self.subTest(i=(line, validation)):
                    self.assertEqual(line, validation)

    def test_write_md(self):
        tf = file_gen.TestFileFetcher(output=out_path_md,
                                      database=db_path, markdown=True)

        urls = file_gen.url_list
        tf.fetch(urls)
        with open(out_path_md, "r") as file:
            for line, validation in zip(file, file_gen.full_md):
                with self.subTest(i=(line, validation)):
                    self.assertEqual(line, validation)
