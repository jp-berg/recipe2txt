import aiohttp
import asyncio
from recipe2txt.utils.misc import Context, dprint, URL, File, Counts
import recipe2txt.html2recipe as h2r
import recipe2txt.sql as sql


class Fetcher:
    def __init__(self, output: File,
                 database: sql.AccessibleDatabase,
                 counts: Counts = Counts(),
                 connections: int = 1,
                 timeout: float = 10.0) -> None:
        self.output: File = output
        self.connections: int = connections
        self.counts: Counts = counts
        self.timeout: float = timeout
        self.db: sql.Database = sql.Database(database, output)

    def get_counts(self) -> Counts:
        return self.counts

    async def _urls2recipes(self, url_queue: asyncio.queues.Queue[URL], timeout: aiohttp.client.ClientTimeout) -> None:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while not url_queue.empty():
                try:
                    url = await url_queue.get()
                    context: Context = dprint(4, "Fetching", url)
                    async with session.get(url) as response:
                        html = await response.text()
                    self.counts.reached += 1

                except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                    dprint(1, "Issue reaching", url)
                    self.db.insert_recipe_unreachable(url)
                    continue

                p = h2r.html2parsed(url, html)
                if not p:
                    self.db.insert_recipe_unknown(url)
                    continue
                r = h2r.parsed2recipe(url, p)
                self.db.insert_recipe(r)

    async def fetch(self, urls: set[URL]) -> None:
        self.counts.urls += len(urls)
        urls = self.db.urls_to_fetch(urls)
        self.counts.require_fetching += len(urls)
        q: asyncio.queues.Queue[URL] = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls) * self.timeout, connect=self.timeout,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._urls2recipes(q, timeout)) for i in range(self.connections)]
        await(asyncio.gather(*tasks))

        recipes = []
        for recipe in self.db.get_recipes():
            r = h2r.recipe2txt(recipe, self.counts)
            if r:
                recipes.append(r)

        with open(self.output, "w") as file:
            dprint(3, "Writing recipes to", self.output)
            file.writelines(recipes)
