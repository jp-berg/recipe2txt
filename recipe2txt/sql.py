import sqlite3
from typing import Final
from .utils.misc import *

_CREATE_TABLES: Final[str] = """
CREATE TABLE IF NOT EXISTS recipes(
	recipeID      INTEGER NOT NULL,
	url	      TEXT NOT NULL UNIQUE,
	status	      TEXT NOT NULL,
	last_fetched  TEXT DEFAULT (datetime()),
	host	      TEXT,
	title	      TEXT,
	total_time    INTEGER,
	image	      TEXT,
	ingredients   TEXT,
	instructions  TEXT,
	yields	      TEXT,
	nutrients     TEXT,
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
	FOREIGN KEY(fileID) REFERENCES files(fileID) ON DELETE CASCADE,
	FOREIGN KEY(recipeID) REFERENCES recipes(recipeID) ON DELETE CASCADE
) STRICT;
"""

_INSERT_RECIPE: Final[str] = "INSERT INTO recipes" \
                             " ( url, status, host, title, total_time, image, ingredients, instructions, yields )" \
                             " VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ? )"

_INSERT_FILE: Final[str] = "INSERT INTO files ( filepath ) VALUES ( ? )"

_ASSOCIATE_FILE_RECIPE: Final[str] = "INSERT INTO contents (fileID, recipeID) VALUES (" \
                                     "(SELECT fileID FROM files WHERE filepath = ?)" \
                                     "(SELECT recipeID FROM recipes WHERE url = ?))"

attibutes = ["host", "title", "total_time", "image", "ingredients", "instructions", "yields", "nutrients"]

class data:
    def __init__(self, data_path: File) -> None:
        self.con = sqlite3.connect(data_path)
        self.cur = self.con.cursor()
        self.cur.execute(_CREATE_TABLES)

    def newRecipe(self, url:URL, html):
