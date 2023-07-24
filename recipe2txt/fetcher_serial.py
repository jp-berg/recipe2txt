import urllib.request
import urllib.error
from typing import Literal
from recipe2txt.utils.misc import URL
from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM
from recipe2txt.fetcher_abstract import AbstractFetcher

logger = get_logger(__name__)


class SerialFetcher(AbstractFetcher):
    is_async: Literal[False] = False

    def fetch_url(self, url: URL) -> None:
        with QCM(logger, logger.info, "Fetching %s", url):
            html = None
            try:
                html = urllib.request.urlopen(url, timeout=self.timeout).read()
            except urllib.error.HTTPError as he:
                logger.error("Connection Error: %s", getattr(he, 'message', repr(he)))
            except (TimeoutError, urllib.error.URLError):
                logger.error("Unable to reach Website")
            except Exception as e:
                logger.error("Error: ", exc_info=e)

            if html:
                self.html2db(url, html)
            else:
                self.db.insert_recipe_unreachable(url)

    def fetch(self, urls: set[URL]) -> None:
        urls = super().require_fetching(urls)
        if urls:
            logger.info("--- Fetching missing recipes ---")
            for url in urls:
                self.fetch_url(url)
        lines = self.gen_lines()
        self.write(lines)
