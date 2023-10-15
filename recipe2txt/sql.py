# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.
"""
Module facilitating the interaction of the program with the database (i.e. the cache).

The database is a Sqlite3-database.
Attributes:
    logger (logging.Logger): The logger for the module. Receives the constructed logger from
            :py:mod:`recipe2txt.utils.ContextLogger`
    RECIPE_ROW_ATTRIBUTES (list[LiteralString]): Contains the names of all rows in the table 'recipes'.
    :py:data:`html2recipe.RECIPE_ATTRIBUTES` represents a subset of this list.
    AccessibleDatabase (NewType): Type representing a database file, that was (at one point during program
    execution) a valid and accessible Sqlite3-database
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Final, NewType, Optional, Tuple, TypeGuard

from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.conditional_imports import LiteralString
from .html2recipe import (METHODS, NA, RECIPE_ATTRIBUTES, SCRAPER_VERSION,
                          Recipe)
from .html2recipe import RecipeStatus as RS
from .html2recipe import gen_status, int2status, none2na
from .utils.misc import *

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from :py:mod:`recipe2txt.utils.ContextLogger`"""

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
"""Contains the names of all rows in the table 'recipes'."""

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

AccessibleDatabase = NewType("AccessibleDatabase", Path)
"""Type representing a database file, that was (at one point during program execution) a valid and accessible
Sqlite3-database"""


def is_accessible_db(path: Path) -> TypeGuard[AccessibleDatabase]:
    """Checks if the file 'path' points to is an :py:data:`AccessibleDatabase`"""
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


def ensure_accessible_db_critical(*path_elem: str | Path) -> AccessibleDatabase:
    """
    Tries to find (or create if not existing) a valid database file from the path elements provided.

    Works like :py:function:`recipe2txt.utils.misc.ensure_accessible_file_critical`.
    Args:
        *path_elem: The elements from which a path should be constructed
    Returns:
        A path to a valid Sqlite3-database-file, which is accessible by this program
    Raises:
        SystemExit: If the database-file cannot be created.

    """
    db_path = full_path(*path_elem)
    directory = ensure_existence_dir_critical(db_path.parent)
    if is_accessible_db(db_path):
        db_file = db_path
    else:
        logger.critical("Database not accessible: %s", db_path)
        sys.exit(os.EX_IOERR)
    return db_file


def fetch_again(status: RS, scraper_version: str) -> bool:
    """
    Decides whether a recipe should be fetched again.

    When a recipe is saved initially it receives a status. Depending on this status and depending on the scraper_version
    the program will not just use the cache data, but tries to scrape the recipe a second time from the web. This will
    happen always for recipes that were previously unreachable. If the requested recipes came from an unknown side or
    were incomplete in some way the recipes will only be fetched again, if the scraper_version currently in use is
    higher than the scraper-version from the last time the recipe was fetched.

    Args:
        status: Indicating the current status of the recipe-entry
        scraper_version: the version-number of :py:mod:`recipe_scrapers` stored with the recipe-entry. Corresponds to
            the version number of the scraper last used on the entry.

    Returns:
        Whether the recipe should be scraped again.
    """
    if status in (RS.UNREACHABLE, RS.NOT_INITIALIZED):
        return True

    if status in (RS.INCOMPLETE_ESSENTIAL, RS.UNKNOWN, RS.INCOMPLETE_ON_DISPLAY, RS.COMPLETE_ON_DISPLAY) \
            and scraper_version < SCRAPER_VERSION:
        return True

    return False


class Database:
    """
    The interface between the program and the cache (i.e. the Sqlite3-database).

    All interaction between the database and the program (inserting, retrieving etc.) runs through this class.
    The connection to the database is maintained for the lifetime of this class. Call :py:meth:`Database.close` to
    release the connection, when this class is no longer required.

    The database remembers which recipes are associated with which files (e.g. which recipe will be written to which
    file. Although not currently used this will hopefully allow to insert new information into old recipe-files without
    overwriting them in the future (Currently old files simply get overwritten).

    The primary key for each :py:class:`html2recipe.Recipe` stored in the database is the
    :py:attr:`html2recipe.Recipe.url`.

    Attributes:
        con: The connection to the database
        cur: The cursor used by this class
        filepath: The path to the recipe-file. All recipes touched during the lifetime of this class will be associated
            with this file.
    """

    def __init__(self, database: AccessibleDatabase, output_file: File) -> None:
        """
        Initializes an instance of the database.

        There should be one instance per output_file. Creates all the necessary tables if not available.

        Args:
            database: The database to be used as cache
            output_file: The path to the file that the recipes will be written to
        """
        self.con = sqlite3.connect(database)
        self.cur = self.con.cursor()
        self.cur.executescript(_CREATE_TABLES)
        self.filepath = str(output_file)
        self.cur.execute(_INSERT_FILE, (self.filepath,))
        self.con.commit()

    def new_recipe(self, recipe: Recipe) -> Recipe:
        """
        Inserts a new recipe into the database

        Will silently skip insertion if the url of this recipe is already in the cache. Use
        :py:meth:`Database.insert_recipe`, if the recipe-entry in the cache should be updated or
        :py:meth:`Database.replace_recipe`, if recipe should replace the recipe-entry in the cache completely.
        """
        self.cur.execute(_INSERT_RECIPE, tuple(recipe))
        self.cur.execute(_ASSOCIATE_FILE_RECIPE, (self.filepath, recipe.url))
        self.con.commit()
        return recipe

    def replace_recipe(self, recipe: Recipe) -> Recipe:
        """Inserts a new recipe into the database or replaces an existing recipe (if the urls are the same)."""
        self.cur.execute(_INSERT_OR_REPLACE_RECIPE, tuple(recipe))
        self.cur.execute(_ASSOCIATE_FILE_RECIPE, (self.filepath, recipe.url))
        self.con.commit()
        return recipe

    def get_recipe_row(self, url: URL) -> Optional[Tuple[Any, ...]]:
        """Retrieves the entry that matches url from the recipe-table and returns the tuple if there was a match."""
        self.cur.execute(_GET_RECIPE, (url,))
        r = self.cur.fetchone()
        return tuple(r) if r else None

    def get_recipe(self, url: URL) -> Recipe:
        """Retrieves the entry that matches url from the recipe-table and returns a :py:class:`html2recipe.Recipe`."""
        if row := self.get_recipe_row(url):
            row = none2na(row)
            row = int2status(row)
        r = Recipe(*row)  # type: ignore[misc]
        return r

    def get_recipes(self) -> list[Recipe]:
        """Retrieves all recipes associated with :py:attr:`Database.filepath`"""
        self.cur.execute(_GET_RECIPES, (self.filepath,))
        recipes = [Recipe(*int2status(none2na(row))) for row in self.cur.fetchall()]
        return recipes

    def get_titles(self) -> list[tuple[str, str]]:
        """Retrieves all titles and host-names from recipes associated with :py:attr:`Database.filepath`"""
        rows = self.cur.execute(_GET_TITLES_HOSTS, (self.filepath,))
        return rows.fetchall()

    def urls_to_fetch(self, wanted: set[URL]) -> set[URL]:
        """
        Filters for recipes that need to be scraped from the web.

        If the URL is already in the cache, :py:func:`fetch_again` decides whether the recipe should be scraped again.

        Args:
            wanted: URLs of the recipes that are wanted

        Returns:
            URLs of the recipes that should be fetched (again).
        """
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
        """Mark the recipe associated with url as 'unreachable' (if url is unknown to the cache)."""
        r = Recipe(url=url, status=RS.UNREACHABLE, scraper_version=SCRAPER_VERSION)
        return self.insert_recipe(r)

    def insert_recipe_unknown(self, url: URL) -> Recipe:
        """Mark the recipe associated with url as 'unknown' (if url is unknown to the cache)."""
        r = Recipe(url=url, status=RS.UNKNOWN, scraper_version=SCRAPER_VERSION)
        return self.insert_recipe(r)

    def insert_recipe(self, recipe: Recipe, prefer_new: bool = False) -> Recipe:
        """
        Inserts a recipe into the cache.

        If an entry with the same url-attribute already exists in the database, the information from recipe and the
        entry are merged. The value of each attribute of the merged recipe/entry is selected from either recipe or the
        entry, depending on which instance has the information or if new information is preferred over old ones. 'None'-
        or :py:data:`html2recipe.NA`-values are always replaced if possible.

        The intent is to update recipes over time, hopefully reducing NA-values to a minimum.

        Args:
            recipe: The recipe to insert
            prefer_new: Whether new values should replace old ones, if non-NA-non-None-values are available for recipe
            and entry.

        Returns:
            An updated recipe.
        """
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
                if not old_row[-2] <= RS.UNKNOWN and new_row[-2] < RS.UNKNOWN:  # type: ignore[operator]
                    merged_row[-2] = gen_status(merged_row[:len(METHODS)])  # type: ignore[arg-type]
                else:
                    merged_row[-2] = max(old_row[-2], new_row[-2])
                r = Recipe(*merged_row)  # type: ignore[arg-type]
                if logger.isEnabledFor(logging.INFO):
                    for attr, old_val, new_val, is_replaced in zip(RECIPE_ATTRIBUTES, old_row, new_row, updated):
                        if is_replaced:
                            logger.info("%s: %s => %s", attr, head_str(old_val), head_str(new_val))
                self.replace_recipe(r)
            else:
                r = Recipe(*merged_row)  # type: ignore[arg-type]
            return r
        else:
            self.new_recipe(recipe)
            return recipe

    def get_contents(self) -> list[URL]:
        """Get all URLs associated with this :py:attr:`filepath`."""
        self.cur.execute(_GET_CONTENT, (self.filepath,))
        urls = [URL(url[0]) for url in self.cur.fetchall()]
        return urls

    def set_contents(self, urls: set[URL]) -> None:
        """Associates all URLs in urls with :py:attr:`filepath`."""
        file_url = [(self.filepath, url) for url in urls]
        self.cur.executemany(_ASSOCIATE_FILE_RECIPE, file_url)
        self.con.commit()

    def empty_db(self) -> None:
        """Removes all data from the database-file"""
        self.cur.executescript(_DROP_ALL)
        self.con.commit()

    def close(self) -> None:
        """
        Closes the cursor and the database connection.

        Using this class after a call to this method will result in errors.
        """
        self.cur.close()
        self.con.close()
