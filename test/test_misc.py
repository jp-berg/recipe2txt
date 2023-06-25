import unittest
import recipe2txt.utils.misc as misc
import os
from .test_helpers import *

testdirs = ["TESTFOLDER1", "TESTFOLDER2"]
testfile = "TESTFILE.txt"
none_dirs = [["/dev", "null"] + testdirs]
normal_dirs = [[folder] + testdirs for folder in tmpdirs]


class FileTests(unittest.TestCase):

    def setUp(self) -> None:
        if not create_tmpdirs():
            self.fail()

    def tearDown(self) -> None:
        if not delete_tmpdirs():
            self.fail()

    def test_extract_urls(self):
        obscured_urls = os.path.join(test_filedir, "permanent", "obscured_urls.txt")
        unobscured_urls = os.path.join(test_filedir, "permanent", "unobscured_urls.txt")
        if not os.path.isfile(obscured_urls):
            self.fail(f"{obscured_urls} does not exist.")
        if not os.path.isfile(unobscured_urls):
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
            ([".", "file"], os.path.join(os.getcwd(), "file"))
        ]

        for test, validation in params:
            with self.subTest(i=test):
                self.assertEqual(misc.full_path(*test), validation)

    def test_ensure_existence_dir(self):
        params_path = [(test, os.path.join(*test)) for test in normal_dirs]

        for test, validation in params_path:
            with self.subTest(i=test):
                self.assertTrue(os.path.samefile(misc.ensure_existence_dir(*test), validation))
                os.removedirs(validation)

        for test in none_dirs:
            with self.subTest(i=test):
                self.assertIsNone(misc.ensure_existence_dir(*test))

    def test_ensure_accessible_file(self):
        params_path = [(test, os.path.join(*test, testfile)) for test in normal_dirs]
        for test, validation in params_path:
            with self.subTest(i=test):
                self.assertTrue(os.path.samefile(misc.ensure_accessible_file(testfile, *test), validation))
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
            self.assertIsNone(misc.ensure_accessible_file(testfile, *test))

    def test_read_files(self):
        file1_content = ["one", "two", "three", "four"]
        file2_content = ["five", "six", "seven", "eight"]

        file1_path = os.path.join(test_project_tmpdir, "testfile1.txt")
        file2_path = os.path.join(xdg_tmpdir, "testfile2.txt")
        file_notafile_path = os.path.join(test_project_tmpdir, "NOTAFILE")

        with open(file1_path, "w") as file:
            for line in file1_content:
                file.write(line + os.linesep)
        with open(file2_path, "w") as file:
            for line in file2_content:
                file.write((line + os.linesep))

        str_list = misc.read_files(file1_path, file_notafile_path, file2_path)

        for test, validation in zip(str_list, (file1_content + file2_content)):
            with self.subTest(i=validation):
                self.assertEqual(test.rstrip(), validation)

        os.remove(file1_path)
        os.remove(file2_path)


class StrTests(unittest.TestCase):

    def test_cutoff(self):
        urls = [("https://www.shop.com/product?utm_source=searchpage", "https://www.shop.com/product"),
                ("https://www.info.net/important-message?user-id:12345", "https://www.info.net/important-message"),
                ("http://www.blog.org/entry1/ref=referer", "http://www.blog.org/entry1")]

        for url, validation in urls:
            with self.subTest(i=url):
                self.assertEqual(misc.cutoff(url, "?", "/ref="), validation)

    def test_dict2str(self):
        dicts = [({1: "one", 2: "two", 3: "three"}, os.linesep.join(["1: one", "2: two", "3: three"])),
                 ({"one": "Eins", "two": "Zwei", "three": "Drei"},
                  os.linesep.join(["one: Eins", "two: Zwei", "three: Drei"]))]

        for d, validation in dicts:
            with self.subTest(i=d):
                self.assertEqual(misc.dict2str(d), validation)

    def test_head_str(self):
        objects = [("teststringteststringteststring", "teststr..."),
                   ("teststring", "teststring"),
                   ("test       ", "test..."),
                   ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "[1, 2,...")]

        for obj, validation in objects:
            with self.subTest(i=obj):
                self.assertEqual(misc.head_str(obj, 10), validation)
