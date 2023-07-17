import os
from xdg_base_dirs import xdg_data_home
from pathlib import Path
from tempfile import gettempdir
from typing import Final
from shutil import rmtree
import recipe2txt.html2recipe as h2r
import recipe2txt.utils.misc as misc
from recipe2txt.utils.ContextLogger import disable_loggers

disable_loggers()

__all__ = ["test_project_tmpdir", "xdg_tmpdir", "tmpdir", "tmpdir_name", "filedir_name",
           "test_filedir", "tmpdirs", "create_tmpdirs", "delete_tmpdirs", "test_recipes", "is_accessible_file"]

tmpdir_name: Final[str] = "tmp_testfiles_re2txt"
filedir_name: Final[str] = "testfiles"

test_filedir: Final[Path] = Path(__file__).parent / "testfiles"

test_project_tmpdir: Final[Path] = Path(test_filedir, tmpdir_name)
xdg_tmpdir: Final[Path] = Path(xdg_data_home(), tmpdir_name)
tmpdir: Final[Path] = Path(gettempdir(), tmpdir_name)

tmpdirs:Final[list[Path]] = [test_project_tmpdir, xdg_tmpdir, tmpdir]

for directory in tmpdirs:
    directory.mkdir(parents=True, exist_ok=True)


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
        if not directory.is_dir():
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError:
                res = res and False
    return res


def delete_tmpdirs() -> bool:
    res = True
    for directory in tmpdirs:
        if directory.is_dir():
            try:
                rmtree(directory)
            except OSError:
                res = res and False
    return res


def is_accessible_file(file: Path, not_empty: bool=False) -> bool:
    if not file.is_file():
        return False
    with file.open("r") as f:
        if not f.readable():
            return False
    with file.open("w") as f:
        if not f.writable():
            return False
    if not_empty and file.stat().st_size == 0:
        return False
    return True




