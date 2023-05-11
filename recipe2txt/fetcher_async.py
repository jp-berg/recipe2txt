import aiohttp
import asyncio
from recipe2txt.utils.misc import dprint, URL, mark_stage
from recipe2txt.fetcher_abstract import AbstractFetcher


class AsyncFetcher(AbstractFetcher):

    def fetch(self, urls: set[URL]) -> None:
        urls = super().require_fetching(urls)
        if urls:
            mark_stage("Fetching missing recipes")
            asyncio.run(self._fetch(urls))
        super().write()

    async def _fetch(self, urls: set[URL]) -> None:
        q: asyncio.queues.Queue[URL] = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls) * self.timeout, connect=self.timeout,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._fetch_task(q, timeout)) for i in range(self.connections)]
        await(asyncio.gather(*tasks))

    async def _fetch_task(self, url_queue: asyncio.queues.Queue[URL], timeout: aiohttp.client.ClientTimeout) -> None:
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