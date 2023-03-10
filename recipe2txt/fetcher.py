import aiohttp
import asyncio
from recipe2txt.utils.misc import Context, dprint, while_context, URL, Counts
import recipe2txt.html2recipe as h2r
from os.path import isfile


class Fetcher:
    def __init__(self, counts: Counts, recipe_file: str, known_urls_file: str) -> None:
        self.counts: Counts = counts

        if isfile(recipe_file):
            self.recipe_file: str = recipe_file
        else:
            raise ValueError("recipe_file does not exist")

        if isfile(known_urls_file):
            self.known_urls_file: str = known_urls_file
        else:
            raise ValueError("known_urls_file does not exist")

    async def _urls2recipes(self, url_queue: asyncio.queues.Queue, timeout: aiohttp.client.ClientTimeout) -> None:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while not url_queue.empty():
                try:
                    url = await url_queue.get()
                    context: Context = dprint(4, "Fetching", url)
                    context = while_context(context)
                    async with session.get(url) as response:
                        html = await response.text()
                    self.counts.reached += 1

                except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                    dprint(1, "\t", "Issue reaching website, skipping...", context=context)
                    continue

                p = h2r.html2parsed(url, html, context)
                if not p: continue
                r = h2r.parsed2recipe(url, p, context, self.counts)
                if not r: continue

                with open(self.recipe_file, 'a') as file:
                    file.write(r)
                with open(self.known_urls_file, 'a') as file:
                    file.write(url)

    async def fetch(self, urls: set[URL], connections: int = 4) -> None:
        q: asyncio.queues.Queue = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls), connect=1,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._urls2recipes(q, timeout)) for i in range(connections)]
        await(asyncio.gather(*tasks))
    