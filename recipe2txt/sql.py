import sqlite3
from os import linesep
from typing import Final, Tuple, Optional, TypeGuard, NewType
from .utils.misc import *
from .html2recipe import Recipe, NA, recipe_attributes, SCRAPER_VERSION, gen_status, RecipeStatus as RS, none2na

_CREATE_TABLES: Final[str] = """
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
) STRICT;
"""

recipe_row_attributes: Final[list[str]] = recipe_attributes + [
    "recipeID",
    "last_fetched"
]

_INSERT_RECIPE: Final[str] = "INSERT OR IGNORE INTO recipes" + \
                             " (" + ", ".join(recipe_attributes) + ")" + \
                             " VALUES (" + ("?," * len(recipe_attributes))[:-1] + ")"

_INSERT_OR_REPLACE_RECIPE: Final[str] = "INSERT OR REPLACE INTO recipes" + \
                                        " (" + ", ".join(recipe_attributes) + ")" + \
                                        " VALUES (" + ("?," * len(recipe_attributes))[:-1] + ")"

_INSERT_FILE: Final[str] = "INSERT OR IGNORE INTO files ( filepath ) VALUES ( ? )"

_ASSOCIATE_FILE_RECIPE: Final[str] = "INSERT OR IGNORE INTO contents (fileID, recipeID) VALUES (" \
                                     " (SELECT fileID FROM files WHERE filepath = ?)," \
                                     " (SELECT recipeID FROM recipes WHERE url = ?))"

_FILEPATHS_JOIN_RECIPES: Final[str] = " ((SELECT * FROM files WHERE filepath = ?) " \
                                      " NATURAL JOIN contents NATURAL JOIN recipes) "
_GET_RECIPE: Final[str] = "SELECT " + ", ".join(recipe_attributes) + " FROM recipes WHERE url = ?"
_GET_RECIPES: Final[str] = "SELECT " + ", ".join(recipe_attributes) + " FROM" + _FILEPATHS_JOIN_RECIPES +\
                           "WHERE status >= " + str(int(RS.INCOMPLETE_ON_DISPLAY))
_GET_URLS_STATUS_VERSION: Final[str] = "SELECT url, status, scraper_version FROM recipes"
_GET_CONTENT: Final[str] = "SELECT url FROM" + _FILEPATHS_JOIN_RECIPES

_GET_TITLES_HOSTS: Final[str] = "SELECT title, host FROM" + _FILEPATHS_JOIN_RECIPES + \
                                " WHERE status >= " + str(int(RS.INCOMPLETE_ON_DISPLAY)) \


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
    if status == RS.UNREACHABLE or status == RS.INCOMPLETE_ESSENTIAL:
        return True

    if (status == RS.UNKNOWN
        or status == RS.INCOMPLETE_ON_DISPLAY
        or status == RS.COMPLETE_ON_DISPLAY) \
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

    def get_recipe_row(self, url: URL) -> Optional[Tuple]:
        self.cur.execute(_GET_RECIPE, (url,))
        r = self.cur.fetchone()
        return r

    def get_recipe(self, url: URL) -> Optional[Recipe]:
        row = self.get_recipe_row(url)
        if row:
            row = none2na(row)
        r = Recipe(*row) # type: ignore
        return r

    def get_recipes(self) -> list[Recipe]:
        self.cur.execute(_GET_RECIPES, (self.filepath,))
        recipes = [Recipe(*none2na(row)) for row in self.cur.fetchall()]
        return recipes

    def get_titles(self) -> list[tuple[str, str]]:
        rows = self.cur.execute(_GET_TITLES_HOSTS, (self.filepath,))
        return rows.fetchall()

    def urls_to_fetch(self, wanted: set[URL]) -> set[URL]:
        self.cur.execute(_GET_URLS_STATUS_VERSION)
        available = self.cur.fetchall()
        for url, status, version in available:
            if url in wanted and not fetch_again(status, version):
                dprint(3, "Using cached version of", url)
                if status <= RS.UNKNOWN: print(status)
                wanted.remove(url)
                if not wanted: break
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
                if new_val and new_val != NA:
                    if old_val and old_val != NA:
                        if prefer_new:
                            merged_row.append(new_val)
                            updated.append(True)
                        else:
                            merged_row.append(old_val)
                            updated.append(False)
                    else:
                        merged_row.append(new_val)
                        updated.append(True)
                else:
                    merged_row.append(old_val)
                    updated.append(False)

            merged_row[-1] = SCRAPER_VERSION
            if True in updated:
                merged_row[-2] = gen_status(merged_row)  # type: ignore
                r = Recipe(*merged_row)  # type: ignore
                replaced_list = ["\t{}: {} => {}".format(attr, head_str(old_val), head_str(new_val))
                            for attr, old_val, new_val, is_replaced in zip(recipe_attributes, old_row, new_row, updated)
                            if is_replaced]
                replaced = linesep + linesep.join(replaced_list)
                dprint(3, "Updated " + recipe.url + "", replaced)
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

    def __del__(self):
        self.cur.close()
        self.con.close()

