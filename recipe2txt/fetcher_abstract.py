from sys import version_info
from os import linesep
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import URL, File, Counts
import recipe2txt.sql as sql
import recipe2txt.html2recipe as h2r
from recipe2txt.utils.markdown import *
from abc import ABC, abstractmethod
if version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum # type: ignore

logger = get_logger(__name__)


class Cache(StrEnum):
    default = "default"
    only = "only"
    new = "new"


class AbstractFetcher(ABC):

    def __init__(self, output: File,
                 database: sql.AccessibleDatabase,
                 counts: Counts = Counts(),
                 timeout: float = 10.0,
                 connections: int = 1,
                 markdown: bool = False,
                 cache: Cache = Cache.default) -> None:
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

    def write(self) -> None:
        recipes = [formatted for recipe in self.db.get_recipes()
                   if (formatted := h2r.recipe2out(recipe, self.counts, md=self.markdown))]

        if len(recipes) > 2:
            titles_raw = self.db.get_titles()
            if self.markdown:
                titles_md_fmt = [section_link(esc(name), fragmentified=True) + " - " + esc(host) + linesep
                                 for name, host in titles_raw]
                titles = ordered(*titles_md_fmt)
            else:
                titles_txt_fmt = [name + " - " + host for name, host in titles_raw]
                titles = linesep.join(titles_txt_fmt)

        with open(self.output, "w") as file:
            logger.info("--- Writing to output ---")
            logger.info("Writing to %s", self.output)
            if len(recipes) > 2:
                file.writelines(titles)
                file.write(paragraph())
                file.write(("-" * 10) + h2r.head_sep)
                file.write(paragraph())
            file.writelines(recipes)
