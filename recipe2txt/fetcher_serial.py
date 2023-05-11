import urllib.request, urllib.error
from recipe2txt.utils.misc import dprint, URL, mark_stage, while_context
from recipe2txt.fetcher_abstract import AbstractFetcher


class SerialFetcher(AbstractFetcher):

    def fetch_url(self, url: URL) -> None:
        ctx = dprint(4, "Fetching", url)
        ctx = while_context(ctx)
        try:
            html = urllib.request.urlopen(url, timeout=self.timeout).read()
            self.html2db(url, html)
        except AttributeError:
            dprint(1, "\t", "Error while parsing", context=ctx)
        except (TimeoutError, urllib.error.URLError):
            dprint(1, "\t", "Website not reachable", context=ctx)
        except urllib.error.HTTPError as he:
            dprint(1, "\t", "Connection Error:", getattr(he, 'message', repr(he)), context=ctx)
        except Exception as e:
            dprint(1, "\t", "Error:", getattr(e, 'message', repr(e)), context=ctx)

    def fetch(self, urls: set[URL]) -> None:
        urls = super().require_fetching(urls)
        if urls:
            mark_stage("Fetching missing recipes")
            for url in urls:
                self.fetch_url(url)
        self.write()
