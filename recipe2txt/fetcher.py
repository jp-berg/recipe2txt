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
Contains the Fetcher-class and an Enum to support that class

Attributes:
    logger (logging.Logger): The logger for the module. Receives the constructed logger from
        :py:mod:`recipe2txt.utils.ContextLogger`
"""
import urllib.request
import urllib.error
from os import linesep

from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM
from recipe2txt.utils.misc import URL, File, Counts
import recipe2txt.sql as sql
import recipe2txt.html2recipe as h2r
from recipe2txt.utils.markdown import *
from recipe2txt.utils.conditional_imports import StrEnum

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from :py:mod:`recipe2txt.utils.ContextLogger`"""


class Cache(StrEnum):
    """
    Enum describing the three different cache-usage-strategies of :py:class:`AbstractFetcher`
    """
    default = "default"
    only = "only"
    new = "new"


class Fetcher:
    """
    Responsible for obtaining missing urls from the web and writing them to a file.

    Class Variables:
        is_async(bool): Whether the class is asynchronous regarding fetching the urls from the internet.
    """
    is_async: bool = False

    def __init__(self, output: File,
                 database: sql.AccessibleDatabase,
                 counts: Counts = Counts(),
                 timeout: float = 10.0,
                 connections: int = 1,
                 markdown: bool = False,
                 cache: Cache = Cache.default) -> None:
        """
        Initializes the Fetcher-class.

        Args:
            output (): Write-destination of the obtained recipes
            database (): The database that stores the recipes and where they have been written to (the cache)
            counts (): For gathering statistics
            timeout (): Maximum waiting time for a response from a server
            connections (): The maximum number of simultaneous connections the Fetcher is allowed to make
            markdown (): Whether the output-file is formatted in Markdown
            cache (): How the cache should be used
        """
        self.output: File = output
        self.counts: Counts = counts
        self.timeout: float = timeout
        self.connections: int = connections
        self.db: sql.Database = sql.Database(database, output)
        self.markdown = markdown
        self.cache = cache

    def get_counts(self) -> Counts:
        return self.counts

    def html2db(self, url: URL, html: str) -> None:
        """
        Turns the HTML into a :py:class:`recipe2txt.html2recipe.Recipe` and stores it in the database.

        Args:
            url (): The URL of the recipe
            html (): The website of the recipe as HTML
        """
        if p := h2r.html2parsed(url, html):
            r = h2r.parsed2recipe(url, p)
            self.db.insert_recipe(r, self.cache == Cache.new)
        else:
            self.db.insert_recipe_unknown(url)

    def require_fetching(self, urls: set[URL]) -> set[URL]:
        """
        Filters all recipes that do not need or should not be retrieved from the web.

        The result heavily depends on the cache-usage-strategy defined by :py:attr:`cache`:
            1.default: Recipes only need to be fetched, if the recipe is either not in the database or if they are
            incomplete.
            2.only: Do not fetch any recipes, only use the information already in the database
            3.new: Fetch recipes from all URLs, regardless of their state in the database
        Args:
            urls (): The URLs, whose recipes should be written to the final file.

        Returns:
            The URLs that the class needs to retrieve from the web according to the cache-usage-strategy
        """
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

    def fetch_urls(self, urls: set[URL]) -> None:
        """
        Fetches the missing URLs from the web and writes the results to the database.

        Args:
            urls (): The URLs from which the method retrieves the recipes
        """
        for url in urls:
            with QCM(logger, logger.info, "Fetching %s", url):
                html = None
                try:
                    html = urllib.request.urlopen(url, timeout=self.timeout).read()
                except urllib.error.HTTPError as e:
                    logger.error("Connection Error: ", exc_info=e)
                except (TimeoutError, urllib.error.URLError) as e:
                    logger.error("Unable to reach Website: ", exc_info=e)
                except Exception as e:
                    if type(e) in (KeyboardInterrupt, SystemExit, MemoryError):
                        raise e
                    logger.error("Error: ", exc_info=e)

                if html:
                    self.html2db(url, html)
                else:
                    self.db.insert_recipe_unreachable(url)

    def fetch(self, urls: set[URL]) -> None:
        """
        Gather the recipes and write them to :py:attr:`output`.

        The urls will be filtered according to the caching-strategy. Recipes that cannot be obtained from cache will
        be retrieved from the web. The recipes will be formatted and then written to the output-file.
        Args:
            urls (): The urls corresponding to the recipes that should be written to the output-file
        """
        urls = self.require_fetching(urls)
        if urls:
            logger.info("--- Fetching missing recipes ---")
            self.fetch_urls(urls)
        lines = self.gen_lines()
        self.write(lines)

    def gen_lines(self) -> list[str]:
        """
        Generates the lines that should be written to the :py:attr:`output`.

        The method obtains the recipes corresponding to :py:attr:`output` from the database, formats them according to
        :py:attr:`markdown` and then concatenates the resulting lines.
        Returns:
            A list, where each item represents a line of the final recipe file
        """
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
        """
        Writes the recipe to :py:attr`output`.
        Args:
            lines (): The lines to be written
        """
        logger.info("--- Writing to output ---")
        logger.info("Writing to %s", self.output)
        self.output.write_text("".join(lines))
