import os
import unittest
from pathlib import Path
from shutil import rmtree

from recipe2txt.sql import is_accessible_db
from recipe2txt.utils.ContextLogger import disable_loggers
from test.test_helpers import test_project_tmpdir, assertAccessibleFile
from test.test_misc import testfile
import recipe2txt.file_setup as fs
from recipe2txt.utils.misc import ensure_existence_dir, full_path

COPY_DEBUG_DATA_DIRECTORY = fs.DEBUG_DATA_DIRECTORY
tmp_data_dir = test_project_tmpdir / "data"
COPY_DEFAULT_OUTPUT_LOCATION_NAME = fs.DEFAULT_OUTPUT_LOCATION_NAME

disable_loggers()


def name_back():
    fs.DEBUG_DATA_DIRECTORY = COPY_DEBUG_DATA_DIRECTORY
    fs.DEFAULT_OUTPUT_LOCATION_NAME = COPY_DEFAULT_OUTPUT_LOCATION_NAME


def remove_dir():
    if tmp_data_dir.is_dir():
        rmtree(tmp_data_dir)


unittest.addModuleCleanup(name_back)
unittest.addModuleCleanup(remove_dir)


class Test(unittest.TestCase):

    def setUp(self) -> None:
        fs.DEBUG_DATA_DIRECTORY = tmp_data_dir
        fs.DEFAULT_OUTPUT_LOCATION_NAME = "NOTAFILE"
        if not ensure_existence_dir(fs.DEBUG_DATA_DIRECTORY):
            self.fail("Could not create %s", fs.DEBUG_DATA_DIRECTORY)

    def tearDown(self) -> None:
        name_back()
        remove_dir()

    def test_file_setup(self):
        db_path = fs.DEBUG_DATA_DIRECTORY / fs.DB_NAME
        log_path = fs.DEBUG_DATA_DIRECTORY / fs.LOG_NAME
        testfile_txt = test_project_tmpdir / testfile
        params = [((True,),
                   (db_path, Path.cwd() / fs.RECIPES_NAME_TXT, log_path)),
                  ((True, str(testfile_txt), False),
                   (db_path, testfile_txt, log_path)),
                  ((True, str(testfile_txt.with_suffix(".md")), True),
                   (db_path, testfile_txt.with_suffix(".md"), log_path))
                  ]

        for idx, (test, validation) in enumerate(params):
            fs.file_setup(*test)
            with self.subTest(i=idx):
                is_accessible_db(validation[0])
                assertAccessibleFile(self, validation[1])
                assertAccessibleFile(self, validation[2])

    def test_get_files(self):
        file1 = fs.DEBUG_DATA_DIRECTORY / "file1"
        file2 = fs.DEBUG_DATA_DIRECTORY / "file2"
        file3 = fs.DEBUG_DATA_DIRECTORY / "file3"

        file1.write_text("TESTFILE")
        file2.write_text("TESTFILE")

        db_path = fs.DEBUG_DATA_DIRECTORY / fs.DB_NAME
        log_path = fs.DEBUG_DATA_DIRECTORY / fs.LOG_NAME
        fs.file_setup(True, file3)

        test_files = set(fs.get_files(True))
        tmp = [file1, file2, file3, db_path, log_path]
        validation_files = {str(file) for file in tmp}

        if diff1 := test_files - validation_files:
            self.fail(f"Files in test_files but not in validation_files: {diff1}")

        if diff2 := validation_files - test_files:
            self.fail(f"Files in validation_files but not in test_files: {diff2}")

    def test_erase_files(self):
        self.assertTrue(fs.DEBUG_DATA_DIRECTORY.is_dir())

        file1 = fs.DEBUG_DATA_DIRECTORY / "file1"
        file2 = fs.DEBUG_DATA_DIRECTORY / "file2"
        file1.write_text("TESTFILE")
        file2.write_text("TESTFILE")
        self.assertTrue(file1.is_file())
        self.assertTrue(file2.is_file())

        fs.erase_files(True)
        self.assertFalse(file1.is_file())
        self.assertFalse(file2.is_file())
        self.assertFalse(fs.DEBUG_DATA_DIRECTORY.is_dir())

    def test_default_output(self):
        testpath = str(full_path(test_project_tmpdir / "out"))
        default_output = fs.DEBUG_DATA_DIRECTORY / fs.DEFAULT_OUTPUT_LOCATION_NAME

        self.assertFalse(default_output.is_file())
        fs.set_default_output(testpath, True)
        self.assertTrue(default_output.is_file())

        content = default_output.read_text().split(os.linesep)
        self.assertEqual(content[0], testpath + ".txt")
        self.assertEqual(content[1], testpath + ".md")

        output = fs.get_default_output(fs.DEBUG_DATA_DIRECTORY, markdown=False)

        self.assertEqual(str(output), testpath + ".txt")
        assertAccessibleFile(self, output)

        with self.assertRaises(SystemExit) as ex:
            fs.set_default_output("/root/recipe", True)
            fs.get_default_output(fs.DEBUG_DATA_DIRECTORY, markdown=False)
            self.assertEqual(ex.exception.code, os.EX_IOERR)

        fs.set_default_output("RESET", True)
        self.assertFalse(default_output.is_file())

        output = fs.get_default_output(fs.DEBUG_DATA_DIRECTORY, markdown=False)

        default_recipe_file = Path.cwd() / fs.RECIPES_NAME_TXT
        assertAccessibleFile(self, default_recipe_file)
        self.assertEqual(output, default_recipe_file)

        os.remove(default_recipe_file)
