import logging
import traceback
import asyncio
from typing import Literal
import aiohttp
from recipe2txt.utils.misc import URL
from recipe2txt.fetcher_abstract import AbstractFetcher
from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM

logger = get_logger(__name__)


class AsyncFetcher(AbstractFetcher):
    is_async: Literal[True] = True

    def fetch(self, urls: set[URL]) -> None:
        urls = super().require_fetching(urls)
        if urls:
            logger.info("--- Fetching missing recipes ---")
            asyncio.run(self._fetch(urls))
        lines = self.gen_lines()
        self.write(lines)

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
                url = await url_queue.get()
                with QCM(logger, logger.info, "Fetching %s", url, defer_emit=True):
                    html = None
                    try:
                        async with session.get(url) as response:
                            html = await response.text()
                        self.counts.reached += 1
                        self.html2db(url, html)
                        continue
                    except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                        logger.error("Unable to reach website")
                        self.db.insert_recipe_unreachable(url)
                    except Exception as e:
                        logger.error("Error while connecting to website: %s", getattr(e, 'message', repr(e)))
                        if logger.isEnabledFor(logging.DEBUG):
                            exception_trace = "".join(traceback.format_exception(e))
                            logger.debug(exception_trace)

                    if html:
                        self.html2db(url, html)
                    else:
                        self.db.insert_recipe_unreachable(url)

