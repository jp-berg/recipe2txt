# Copyright (C) 2024 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt. If not, see <https://www.gnu.org/licenses/>.
"""
Contains the Fetcher-class and an Enum to support that class.

Attributes:
    logger (logging.Logger): The logger for the module. Receives the constructed
    logger from
        :py:mod:`recipe2txt.utils.ContextLogger`
"""
import urllib.error
import urllib.request

import recipe2txt.html2recipe as h2r
from recipe2txt.sql import Database
from recipe2txt.utils.conditional_imports import StrEnum
from recipe2txt.utils.ContextLogger import QueueContextManager as QCM
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import NEVER_CATCH, URL, Counts

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from 
:py:mod:`recipe2txt.utils.ContextLogger`"""


class Cache(StrEnum):
    """
    Enum describing the three different cache-usage-strategies of
    :py:class:`AbstractFetcher`
    """

    DEFAULT = "default"
    ONLY = "only"
    NEW = "new"


class Fetcher:
    """
    Responsible for obtaining missing urls from the web and writing them to a file.

    Class Variables:
        is_async: Whether the class is asynchronous regarding fetching the urls
        from the internet.
    """

    is_async: bool = False
    connections: int = 1
    timeout: float = 10.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101"
        " Firefox/115.0"
    )

    def __init__(
        self,
        database: Database,
        counts: Counts = Counts(),
        timeout: float | None = None,
        connections: int | None = None,
        caching_strategy: Cache = Cache.DEFAULT,
        user_agent: str | None = None,
    ) -> None:
        """
        Initializes the Fetcher-class.

        Args:
            database: The database that stores the recipes and where they have been
            written to (the cache)
            counts: For gathering statistics
            timeout: Maximum waiting time for a response from a server
            connections: The maximum number of simultaneous connections the Fetcher
            is allowed to make
            caching_strategy: How the cache should be used
            user_agent: The user-agent for making http-requests
        """
        self.counts: Counts = counts
        self.timeout: float = timeout if timeout else self.timeout
        self.connections: int = connections if connections else self.connections
        self.db: Database = database
        self.cache = caching_strategy
        self.user_agent = user_agent if user_agent else self.user_agent

    def get_counts(self) -> Counts:
        return self.counts

    def html2db(self, url: URL, html: str) -> None:
        """
        Turns the HTML into a :py:class:`recipe2txt.html2recipe.Recipe` and stores it
        in the database.

        Args:
            url: The URL of the recipe
            html: The website of the recipe as HTML
        """
        if p := h2r.html2parsed(url, html):
            r = h2r.parsed2recipe(p)
            self.db.insert_recipe(r, self.cache == Cache.NEW)
        else:
            self.db.insert_recipe_unknown(url)

    def require_fetching(self, urls: set[URL]) -> set[URL]:
        """
        Filters all recipes that do not need or should not be retrieved from the web.

        The result heavily depends on the cache-usage-strategy defined by
        :py:attr:`cache`:
            1.default: Recipes only need to be fetched, if the recipe is either not
            in the database or if they are incomplete.
            2.only: Do not fetch any recipes, only use the information already in the
            database
            3.new: Fetch recipes from all URLs, regardless of their state in the
            database

        Args:
            urls: The URLs, whose recipes should be written to the final file.

        Returns:
            The URLs that the class needs to retrieve from the web according to the
            cache-usage-strategy
        """
        self.counts.urls += len(urls)
        if self.cache is Cache.ONLY:
            self.db.set_contents(urls)
            urls.clear()
        elif self.cache is Cache.DEFAULT:
            urls = self.db.urls_to_fetch(urls)
        elif self.cache is Cache.NEW:
            self.db.set_contents(urls)
        self.counts.require_fetching += len(urls)
        return urls

    def fetch_urls(self, urls: set[URL]) -> None:
        """
        Fetches the missing URLs from the web and writes the results to the database.

        While using one function to fetch the webpages and another to send the
        collected data to the database might make
        for simpler functions, it was deemed more important to save each recipe to
        disk as soon as possible. This is
        preferred, because fetching recipes is so expensive in terms of time. Writing
        to disk early saves time in
        case of an early termination of the program, since the collected data can be
        fetched from disk on the next run.

        Args:
            urls: The URLs from which the method retrieves the recipes
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
                except NEVER_CATCH:
                    raise
                except Exception as e:
                    logger.error("Error: ", exc_info=e)

                if html:
                    self.html2db(url, html)
                else:
                    self.db.insert_recipe_unreachable(url)

    def fetch(self, urls: set[URL]) -> None:
        """
        Gather the recipes and write them to :py:attr:`output`.

        The urls will be filtered according to the caching-strategy. Recipes that
        cannot be obtained from cache will
        be retrieved from the web. The recipes will be formatted and then written to
        the output-file.

        Args:
            urls: The urls corresponding to the recipes that should be written to the
            output-file
        """
        urls = self.require_fetching(urls)
        if urls:
            logger.info("--- Fetching missing recipes ---")
            self.fetch_urls(urls)
