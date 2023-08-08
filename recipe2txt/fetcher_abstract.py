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

from os import linesep
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import URL, File, Counts
import recipe2txt.sql as sql
import recipe2txt.html2recipe as h2r
from recipe2txt.utils.markdown import *
from abc import ABC, abstractmethod
from recipe2txt.utils.conditional_imports import StrEnum

logger = get_logger(__name__)


class Cache(StrEnum):
    default = "default"
    only = "only"
    new = "new"


class AbstractFetcher(ABC):
    is_async: bool
    connections: int = 1
    timeout: float = 10.0
    user_agent: str = \
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0"

    def __init__(self, output: File,
                 database: sql.AccessibleDatabase,
                 counts: Counts = Counts(),
                 timeout: float | None = None,
                 connections: int | None = None,
                 markdown: bool = False,
                 cache: Cache = Cache.default,
                 user_agent: str | None = None) -> None:
        self.output: File = output
        self.counts: Counts = counts
        self.timeout: float = timeout if timeout else self.timeout
        self.connections: int = connections if connections else self.connections
        self.db: sql.Database = sql.Database(database, output)
        self.markdown = markdown
        self.cache = cache
        self.user_agent = user_agent if user_agent else self.user_agent

    def get_counts(self) -> Counts:
        return self.counts

    def html2db(self, url: URL, html: str) -> None:
        if p := h2r.html2parsed(url, html):
            r = h2r.parsed2recipe(url, p)
            self.db.insert_recipe(r, self.cache == Cache.new)
        else:
            self.db.insert_recipe_unknown(url)

    def require_fetching(self, urls: set[URL]) -> set[URL]:
        self.counts.urls += len(urls)
        if self.cache is Cache.only:
            self.db.set_contents(urls)
            urls.clear()
        elif self.cache is Cache.default:
            urls = self.db.urls_to_fetch(urls)
        elif self.cache is Cache.new:
            urls = urls
            self.db.set_contents(urls)
        self.counts.require_fetching += len(urls)
        return urls

    @abstractmethod
    def fetch(self, urls: set[URL]) -> None:
        pass

    def gen_lines(self) -> list[str]:
        recipes = []
        count = 0
        for recipe in self.db.get_recipes():
            if formatted := h2r.recipe2out(recipe, self.counts, md=self.markdown):
                count += 1
                for line in formatted:
                    recipes.append(line)

        if count > 3:
            titles_raw = self.db.get_titles()
            if self.markdown:
                titles_md_fmt = [f"{section_link(esc(name), fragmentified=True)} - {esc(host)}{linesep}"
                                 for name, host in titles_raw]
                titles = ordered(*titles_md_fmt)
            else:
                titles = [f"{name} - {host}{linesep}" for name, host in titles_raw]
                titles = titles + [paragraph(), ("-" * 10) + linesep*2, paragraph()]
        else:
            titles = []

        return titles + recipes

    def write(self, lines: list[str]) -> None:
        logger.info("--- Writing to output ---")
        logger.info("Writing to %s", self.output)
        self.output.write_text("".join(lines))
