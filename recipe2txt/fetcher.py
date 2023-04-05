from os import linesep

import aiohttp
import asyncio
from recipe2txt.utils.misc import Context, dprint, URL, File, Counts, mark_stage
from recipe2txt.utils.markdown import *
import recipe2txt.html2recipe as h2r
import recipe2txt.sql as sql


class Fetcher:
    def __init__(self, output: File,
                 database: sql.AccessibleDatabase,
                 counts: Counts = Counts(),
                 connections: int = 1,
                 timeout: float = 10.0,
                 markdown: bool = False,
                 ignore_cached: bool = False) -> None:
        self.output: File = output
        self.connections: int = connections
        self.counts: Counts = counts
        self.timeout: float = timeout
        self.db: sql.Database = sql.Database(database, output)
        self.markdown = markdown
        self.ignore_cached = ignore_cached

    def get_counts(self) -> Counts:
        return self.counts

    async def _urls2recipes(self, url_queue: asyncio.queues.Queue[URL], timeout: aiohttp.client.ClientTimeout) -> None:
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

                if p := h2r.html2parsed(url, html):
                    r = h2r.parsed2recipe(url, p)
                    self.db.insert_recipe(r)
                else:
                    self.db.insert_recipe_unknown(url)

    async def fetch(self, urls: set[URL]) -> None:
        self.counts.urls += len(urls)
        if not self.ignore_cached:
            urls = self.db.urls_to_fetch(urls)
        self.counts.require_fetching += len(urls)
        q: asyncio.queues.Queue[URL] = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls) * self.timeout, connect=self.timeout,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._urls2recipes(q, timeout)) for i in range(self.connections)]
        if self.counts.require_fetching:
            mark_stage("Fetching missing recipes")
        await(asyncio.gather(*tasks))
        self.write()

    def write(self):
        titles = self.db.get_titles()
        if self.markdown:
            print(len(titles))
            titles = [section_link(esc(name)) + " - " + esc(host) + linesep for name, host in titles]
            titles = ordered(*titles)
        else:
            titles = [name + " - " + host + linesep for name, host in titles]

        recipes = [formatted for recipe in self.db.get_recipes()
                   if (formatted:= h2r.recipe2out(recipe, self.counts, md=self.markdown))]

        with open(self.output, "w") as file:
            mark_stage("Writing to output")
            dprint(3, "Writing to", self.output)
            file.writelines(titles)
            file.write(paragraph())
            file.write(("-"*10) + h2r.head_sep)
            file.write(paragraph())
            file.writelines(recipes)

