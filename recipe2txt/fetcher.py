from sys import version_info
if version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum
from os import linesep
import urllib.request
import urllib.error
from recipe2txt.utils.misc import dprint, URL, File, Counts, mark_stage, while_context
from recipe2txt.utils.markdown import *
import recipe2txt.html2recipe as h2r
import recipe2txt.sql as sql

_is_async: bool
try:
    import aiohttp
    import asyncio

    _is_async = True
except ModuleNotFoundError:
    print("NO ASYNC")
    _is_async = False


class Cache(StrEnum):
    default = "default"
    only = "only"
    new = "new"


class Fetcher:

    def __init__(self, output: File,
                 database: sql.AccessibleDatabase,
                 counts: Counts = Counts(),
                 connections: int = 1,
                 timeout: float = 10.0,
                 markdown: bool = False,
                 cache: Cache = Cache.default) -> None:
        self.output: File = output
        self.connections: int = connections
        if self.connections == 1 or not _is_async:
            self.is_async = False
        else:
            self.is_async = True
        self.counts: Counts = counts
        self.timeout: float = timeout
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

    def _urls2recipes(self, url: URL) -> None:
        ctx = dprint(4, "Fetching", url)
        ctx = while_context(ctx)
        try:
            html = urllib.request.urlopen(url, timeout=self.timeout).read()
            self.html2db(url, html)
        except AttributeError as ae:
            dprint(1, "\t", "Error while parsing", context=ctx)
        except (TimeoutError, urllib.error.URLError):
            dprint(1, "\t", "Website not reachable", context=ctx)
        except urllib.error.HTTPError as he:
            dprint(1, "\t", "Connection Error:", getattr(he, 'message', repr(he)), context=ctx)
        except Exception as e:
            dprint(1, "\t", "Error:", getattr(e, 'message', repr(e)), context=ctx)

    async def _urls2recipes_a(self, url_queue: asyncio.queues.Queue[URL],
                              timeout: aiohttp.client.ClientTimeout) -> None:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while not url_queue.empty():
                try:
                    url = await url_queue.get()
                    dprint(4, "Fetching", url)
                    async with session.get(url) as response:
                        html = await response.text()
                    self.counts.reached += 1

                except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                    dprint(1, "Issue reaching", url)
                    self.db.insert_recipe_unreachable(url)
                    continue
                self.html2db(url, html)

    def _fetch(self, urls: set[URL]) -> None:
        for url in urls:
            self._urls2recipes(url)

    async def _fetch_a(self, urls: set[URL]) -> None:
        q: asyncio.queues.Queue[URL] = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls) * self.timeout, connect=self.timeout,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._urls2recipes_a(q, timeout)) for i in range(self.connections)]

        await(asyncio.gather(*tasks))

    def fetch(self, urls: set[URL]) -> None:
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
        if self.counts.require_fetching:
            mark_stage("Fetching missing recipes")

        if self.is_async:
            asyncio.run(self._fetch_a(urls))
        else:
            self._fetch(urls)
        self.write()

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
            mark_stage("Writing to output")
            dprint(3, "Writing to", self.output)
            if len(recipes) > 2:
                file.writelines(titles)
                file.write(paragraph())
                file.write(("-" * 10) + h2r.head_sep)
                file.write(paragraph())
            file.writelines(recipes)
