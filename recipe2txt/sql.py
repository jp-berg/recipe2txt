import logging
import sqlite3
from os import linesep
from typing import Final, Tuple, Optional, TypeGuard, NewType, Any
from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.utils.ContextLogger import get_logger
from .utils.misc import *
from .html2recipe import Recipe, NA, RECIPE_ATTRIBUTES, SCRAPER_VERSION, gen_status, RecipeStatus as RS, none2na, \
    int2status, METHODS, RecipeStatus

logger = get_logger(__name__)
_CREATE_TABLES: Final[LiteralString] = """
CREATE TABLE IF NOT EXISTS recipes(
	recipeID        INTEGER NOT NULL,
	url             TEXT NOT NULL UNIQUE,
	status	        INTEGER NOT NULL,
	last_fetched    TEXT DEFAULT (datetime()),
	scraper_version TEXT,
	host	        TEXT,
	title	        TEXT,
	total_time      TEXT,
	image	        TEXT,
	ingredients     TEXT,
	instructions    TEXT,
	yields	        TEXT,
	nutrients       TEXT,
	PRIMARY KEY(recipeID AUTOINCREMENT)
) STRICT;
CREATE TABLE IF NOT EXISTS files(
	fileID	      INTEGER NOT NULL,
	filepath      TEXT NOT NULL UNIQUE,
	last_changed  TEXT DEFAULT (datetime()),
	PRIMARY KEY(fileID AUTOINCREMENT)
) STRICT;
CREATE TABLE IF NOT EXISTS contents(
	fileID	 INTEGER NOT NULL,
	recipeID INTEGER NOT NULL,
	FOREIGN KEY(fileID) REFERENCES files(fileID) ON UPDATE CASCADE ON DELETE CASCADE,
	FOREIGN KEY(recipeID) REFERENCES recipes(recipeID) ON UPDATE CASCADE ON DELETE CASCADE
	UNIQUE(fileID, recipeID) ON CONFLICT IGNORE
) STRICT;
"""

RECIPE_ROW_ATTRIBUTES: Final[list[LiteralString]] = RECIPE_ATTRIBUTES + [
    "recipeID",
    "last_fetched"
]

_INSERT_RECIPE: Final[str] = "INSERT OR IGNORE INTO recipes" + \
                             " (" + ", ".join(RECIPE_ATTRIBUTES) + ")" + \
                             " VALUES (" + ("?," * len(RECIPE_ATTRIBUTES))[:-1] + ")"

_INSERT_OR_REPLACE_RECIPE: Final[str] = "INSERT OR REPLACE INTO recipes" + \
                                        " (" + ", ".join(RECIPE_ATTRIBUTES) + ")" + \
                                        " VALUES (" + ("?," * len(RECIPE_ATTRIBUTES))[:-1] + ")"

_INSERT_FILE: Final[LiteralString] = "INSERT OR IGNORE INTO files ( filepath ) VALUES ( ? )"

_ASSOCIATE_FILE_RECIPE: Final[LiteralString] = "INSERT OR IGNORE INTO contents (fileID, recipeID) VALUES (" \
                                     " (SELECT fileID FROM files WHERE filepath = ?)," \
                                     " (SELECT recipeID FROM recipes WHERE url = ?))"

_FILEPATHS_JOIN_RECIPES: Final[LiteralString] = " ((SELECT * FROM files WHERE filepath = ?) " \
                                      " NATURAL JOIN contents NATURAL JOIN recipes) "
_GET_RECIPE: Final[LiteralString] = "SELECT " + ", ".join(RECIPE_ATTRIBUTES) + " FROM recipes WHERE url = ?"
_GET_RECIPES: Final[str] = "SELECT " + ", ".join(RECIPE_ATTRIBUTES) + " FROM" + _FILEPATHS_JOIN_RECIPES + \
                           "WHERE status >= " + str(int(RS.INCOMPLETE_ON_DISPLAY))
_GET_URLS_STATUS_VERSION: Final[LiteralString] = "SELECT url, status, scraper_version FROM recipes"
_GET_CONTENT: Final[LiteralString] = "SELECT url FROM" + _FILEPATHS_JOIN_RECIPES

_GET_TITLES_HOSTS: Final[str] = "SELECT title, host FROM" + _FILEPATHS_JOIN_RECIPES + \
                                " WHERE status >= " + str(int(RS.INCOMPLETE_ON_DISPLAY))

_DROP_ALL: Final[LiteralString] = "DROP TABLE IF EXISTS recipes; DROP TABLE IF EXISTS files; " \
                                  "DROP TABLE IF EXISTS contents"

AccessibleDatabase = NewType("AccessibleDatabase", str)


def is_accessible_db(path: str) -> TypeGuard[AccessibleDatabase]:
    try:
        con = sqlite3.connect(path)
    except sqlite3.OperationalError:
        return False
    cur = con.cursor()

    try:
        cur.execute("PRAGMA SCHEMA_VERSION")
    except sqlite3.DatabaseError:
        return False
    finally:
        cur.close()
        con.close()
    return True


def fetch_again(status: RS, scraper_version: str) -> bool:
    if status in (RS.UNREACHABLE, RS.INCOMPLETE_ESSENTIAL, RS.NOT_INITIALIZED):
        return True

    if status in (RS.UNKNOWN, RS.INCOMPLETE_ON_DISPLAY, RS.COMPLETE_ON_DISPLAY) \
            and scraper_version < SCRAPER_VERSION:
        return True

    return False


class Database:
    def __init__(self, database: AccessibleDatabase, output_file: File) -> None:
        self.con = sqlite3.connect(database)
        self.cur = self.con.cursor()
        self.cur.executescript(_CREATE_TABLES)
        self.filepath = output_file
        self.cur.execute(_INSERT_FILE, (output_file,))
        self.con.commit()

    def new_recipe(self, recipe: Recipe) -> Recipe:
        self.cur.execute(_INSERT_RECIPE, tuple(recipe))
        self.cur.execute(_ASSOCIATE_FILE_RECIPE, (self.filepath, recipe.url))
        self.con.commit()
        return recipe

    def replace_recipe(self, recipe: Recipe) -> Recipe:
        self.cur.execute(_INSERT_OR_REPLACE_RECIPE, tuple(recipe))
        self.cur.execute(_ASSOCIATE_FILE_RECIPE, (self.filepath, recipe.url))
        self.con.commit()
        return recipe

    def get_recipe_row(self, url: URL) -> Optional[Tuple[Any, ...]]:
        self.cur.execute(_GET_RECIPE, (url,))
        r = self.cur.fetchone()
        return tuple(r) if r else None

    def get_recipe(self, url: URL) -> Optional[Recipe]:
        if row := self.get_recipe_row(url):
            row = none2na(row)
            row = int2status(row)
        r = Recipe(*row)  # type: ignore
        return r

    def get_recipes(self) -> list[Recipe]:
        self.cur.execute(_GET_RECIPES, (self.filepath,))
        recipes = [Recipe(*int2status(none2na(row))) for row in self.cur.fetchall()]
        return recipes

    def get_titles(self) -> list[tuple[str, str]]:
        rows = self.cur.execute(_GET_TITLES_HOSTS, (self.filepath,))
        return rows.fetchall()

    def urls_to_fetch(self, wanted: set[URL]) -> set[URL]:
        self.cur.execute(_GET_URLS_STATUS_VERSION)
        available = self.cur.fetchall()
        for url, status, version in available:
            if url in wanted and not fetch_again(status, version):
                if status == RS.UNKNOWN:
                    logger.info("Not refetching %s, scraper-version (%s) since last fetch has not changed.",
                                url, version)
                else:
                    logger.info("Using cached version of %s", url)

                wanted.remove(url)
                self.cur.execute(_ASSOCIATE_FILE_RECIPE, (self.filepath, url))
                if not wanted: break
        self.con.commit()
        return wanted

    def insert_recipe_unreachable(self, url: URL) -> Recipe:
        r = Recipe(url=url, status=RS.UNREACHABLE, scraper_version=SCRAPER_VERSION)
        return self.insert_recipe(r)

    def insert_recipe_unknown(self, url: URL) -> Recipe:
        r = Recipe(url=url, status=RS.UNKNOWN, scraper_version=SCRAPER_VERSION)
        return self.insert_recipe(r)

    def insert_recipe(self, recipe: Recipe, prefer_new: bool = False) -> Recipe:
        old_row = self.get_recipe_row(recipe.url)
        new_row = tuple(recipe)
        merged_row = []
        updated = []
        if old_row:
            for old_val, new_val in zip(old_row, new_row):
                if (new_val and new_val != NA) \
                        and (prefer_new or not (old_val and old_val != NA)):
                    merged_row.append(new_val)
                    updated.append(True)
                else:
                    merged_row.append(old_val)
                    updated.append(False)

            merged_row[-1] = SCRAPER_VERSION
            if True in updated:
                if not old_row[-2] <= RS.UNKNOWN and new_row[-2] < RS.UNKNOWN:  # type: ignore
                    merged_row[-2] = gen_status(merged_row[:len(METHODS)])  # type: ignore
                else:
                    merged_row[-2] = max(old_row[-2], new_row[-2])
                r = Recipe(*merged_row)  # type: ignore
                if logger.isEnabledFor(logging.INFO):
                    replaced_list = [f"\t{attr}: {head_str(old_val)} => {head_str(new_val)}"
                                     for attr, old_val, new_val, is_replaced in
                                     zip(RECIPE_ATTRIBUTES, old_row, new_row, updated)
                                     if is_replaced]
                    replaced = linesep + linesep.join(replaced_list)
                    logger.info("Updated %s: %s", recipe.url, replaced)
                self.replace_recipe(r)
            else:
                r = Recipe(*merged_row)  # type: ignore
            return r
        else:
            self.new_recipe(recipe)
            return recipe

    def get_contents(self) -> list[URL]:
        self.cur.execute(_GET_CONTENT, (self.filepath,))
        urls = [URL(url[0]) for url in self.cur.fetchall()]
        return urls

    def set_contents(self, urls: set[URL]) -> None:
        file_url = [(self.filepath, url) for url in urls]
        self.cur.executemany(_ASSOCIATE_FILE_RECIPE, file_url)
        self.con.commit()

    def empty_db(self) -> None:
        self.cur.executescript(_DROP_ALL)
        self.con.commit()

    def close(self) -> None:
        self.cur.close()
        self.con.close()
