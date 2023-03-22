import aiohttp
import asyncio
from recipe2txt.utils.misc import Context, dprint, while_context, URL, File, Counts
import recipe2txt.html2recipe as h2r


class Fetcher:
    def __init__(self, output: File,
                 known_urls_file: File,
                 counts: Counts = Counts(),
                 connections: int = 1,
                 timeout: float = 10.0) -> None:
        self.output: File = output
        self.known_urls_file: File = known_urls_file
        self.connections: int = connections
        self.counts: Counts = counts
        self.timeout: float = timeout

    def get_counts(self) -> Counts:
        return self.counts

    async def _urls2recipes(self, url_queue: asyncio.queues.Queue[URL], timeout: aiohttp.client.ClientTimeout) -> None:
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
                    dprint(1, "\t", "Issue reaching", url, ", skipping...")
                    continue

                p = h2r.html2parsed(url, html, context)
                if not p: continue
                r = h2r.parsed2recipe(url, p, context)
                t = h2r.recipe2txt(r, self.counts)
                if not t: continue

                with open(self.output, 'a') as file:
                    file.write(t)
                with open(self.known_urls_file, 'a') as file:
                    file.write(url)

    async def fetch(self, urls: set[URL]) -> None:
        self.counts.urls += len(urls)
        q: asyncio.queues.Queue[URL] = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls) * self.timeout, connect=self.timeout,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._urls2recipes(q, timeout)) for i in range(self.connections)]
        await(asyncio.gather(*tasks))
    