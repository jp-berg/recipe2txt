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

"""
import asyncio
from typing import Literal
import aiohttp
from recipe2txt.utils.misc import URL
from recipe2txt.fetcher import Fetcher, logger
from recipe2txt.utils.ContextLogger import QueueContextManager as QCM


class AsyncFetcher(Fetcher):
    is_async: Literal[True] = True
    connections = 4

    def fetch_urls(self, urls: set[URL]) -> None:
        asyncio.run(self._fetch(urls))

    async def _fetch(self, urls: set[URL]) -> None:
        q: asyncio.queues.Queue[URL] = asyncio.Queue()
        for url in urls: await q.put(url)
        timeout = aiohttp.ClientTimeout(total=10 * len(urls) * self.timeout, connect=self.timeout,
                                        sock_connect=None, sock_read=None)
        tasks = [asyncio.create_task(self._fetch_task(q, timeout)) for i in range(self.connections)]
        await(asyncio.gather(*tasks))

    async def _fetch_task(self, url_queue: asyncio.queues.Queue[URL], timeout: aiohttp.client.ClientTimeout) -> None:
        async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent" : self.user_agent}) as session:
            while not url_queue.empty():
                url = await url_queue.get()
                with QCM(logger, logger.info, "Fetching %s", url, defer_emit=True):
                    html = None
                    try:
                        async with session.get(url) as response:
                            html = await response.text()
                        self.counts.reached += 1
                    except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError) as e:
                        logger.error("Unable to reach website: ", exc_info=e)
                    except Exception as e:
                        if type(e) in (KeyboardInterrupt, SystemExit, MemoryError):
                            raise e
                        logger.error("Error while connecting to website: ", exc_info=e)
                    if html:
                        self.html2db(url, html)
                    else:
                        self.db.insert_recipe_unreachable(url)
