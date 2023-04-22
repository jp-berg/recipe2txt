import os
from xdg_base_dirs import xdg_data_home
from tempfile import gettempdir
from typing import Final
from shutil import rmtree
import recipe2txt.html2recipe as h2r
import recipe2txt.utils.misc as misc

misc.set_vlevel(0)

__all__ = ["test_project_tmpdir", "xdg_tmpdir", "tmpdir", "tmpdir_name", "filedir_name",
           "test_filedir", "tmpdirs", "create_tmpdirs", "delete_tmpdirs", "test_recipes"]

tmpdir_name: Final[str] = "tmp_testfiles_re2txt"
filedir_name: Final[str] = "testfiles"

test_filedir: Final[str] = os.path.join(os.path.dirname(__file__), "testfiles")
test_project_tmpdir: Final[str] = os.path.join(test_filedir, tmpdir_name)
os.makedirs(test_project_tmpdir, exist_ok=True)

xdg_tmpdir: Final[str] = os.path.join(xdg_data_home(), tmpdir_name)
os.makedirs(xdg_tmpdir, exist_ok=True)

tmpdir: Final[str] = os.path.join(gettempdir(), tmpdir_name)
os.makedirs(tmpdir, exist_ok=True)

tmpdirs:Final[list[str]] = [test_project_tmpdir, xdg_tmpdir, tmpdir]


test_recipes: list[h2r.Recipe] = [
    h2r.Recipe(),
    h2r.Recipe(url=misc.URL("https://www.websitedown.com/recipe1"), status=h2r.RecipeStatus.UNREACHABLE,
               scraper_version=h2r.SCRAPER_VERSION),

    h2r.Recipe(title="Meal", host="incomplete_essential.com", url=misc.URL("https://www.incomplete.essential.com/meal"),
               status=h2r.RecipeStatus.INCOMPLETE_ESSENTIAL, scraper_version=h2r.SCRAPER_VERSION),

    h2r.Recipe(ingredients=os.linesep.join(["1 pinch of salt", "2 spoons of love", "1l water"]),
               instructions=os.linesep.join(["Gather", "Prepare", "Enjoy"]), title="Simple",
               yields="3 portions", url=misc.URL("https://www.notcomplete.net/simple"), host="notcomplete.net",
               status=h2r.RecipeStatus.INCOMPLETE_ON_DISPLAY, scraper_version=h2r.SCRAPER_VERSION),

    h2r.Recipe(ingredients=os.linesep.join(["Ingredient 1", "Ingredient 2", "Ingredient 3"]),
               instructions=os.linesep.join(["Step 1", "Step 2", "Step 3"]), title="Basic", total_time="123",
               yields="4 pieces", host="notcomplete.com", image="notcomplete.net/basic/img.basic-png",
               url=misc.URL("https://www.notcomplete.net/basic"), status=h2r.RecipeStatus.COMPLETE_ON_DISPLAY,
               scraper_version=h2r.SCRAPER_VERSION)
]


def create_tmpdirs() -> bool:
    res = True
    for directory in tmpdirs:
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError:
                res = res and False
    return res


def delete_tmpdirs() -> bool:
    res = True
    for directory in tmpdirs:
        if os.path.isdir(directory):
            try:
                rmtree(directory)
            except OSError:
                res = res and False
    return res




