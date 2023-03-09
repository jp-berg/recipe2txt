import os.path
import validators
from os import getcwd
from xdg_base_dirs import xdg_data_home
import aiohttp
import asyncio
from .utils import misc
from .utils.misc import Context, dprint, while_context, URL, Counts
from typing import Final
from .html2recipe import setup, html2recipe

program_name: Final[str] = "recipes2txt"

known_urls_name: Final[str] = "knownURLs.txt"
recipes_name: Final[str] = "recipes.txt"
default_urls_name: Final[str] = "urls.txt"
counts: Counts = Counts()

known_urls_file: str
url_file: str
recipe_file: str


def file_setup(debug: bool = False) -> None:
    global known_urls_file
    global url_file
    global recipe_file

    workdir: str = os.path.expanduser(os.path.join("~", "Rezepte"))
    default_data_directory: str = os.path.join(xdg_data_home(), program_name)
    if debug:
        workdir = os.path.join(getcwd(), "tests", "testfiles")
        default_data_directory = os.path.join(workdir, "data")
    known_urls_file = misc.ensure_existence_file(known_urls_name, default_data_directory)
    url_file = misc.ensure_existence_file(default_urls_name, workdir)
    recipe_file = misc.ensure_existence_file(recipes_name, workdir)


async def urls2recipes(url_queue: asyncio.queues.Queue, timeout: aiohttp.client.ClientTimeout) -> None:
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not url_queue.empty():
            try:
                url = await url_queue.get()
                context: Context = dprint(4, "Fetching", url)
                context = while_context(context)
                async with session.get(url) as response:
                    html = await response.text()

                counts.reached += 1
                html2recipe(url, html)

            except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                dprint(1, "\t", "Issue reaching website, skipping...", context=context)


def process_urls(known_urls: set[URL], strings: list[str]) -> set[URL]:
    processed: set[URL] = set()
    for string in strings:
        string = string.replace(os.linesep, '')
        string.strip()
        if not string.startswith("http"):
            string = "http://" + string
        if validators.url(string):
            url: URL = URL(string)
            url = misc.cutoff(url, "/ref=", "?")
            if url in known_urls:
                dprint(3, "Already scraped:", url)
                continue
            if url in processed:
                dprint(3, "Already queued:", url)
            else:
                processed.add(url)
        else:
            dprint(3, "Not an URL:", string)
    return processed


async def fetch(urls: set[URL]) -> None:
    q: asyncio.queues.Queue = asyncio.Queue()
    for url in urls: await q.put(url)
    timeout = aiohttp.ClientTimeout(total=10 * len(urls), connect=1,
                                    sock_connect=None, sock_read=None)
    tasks = [asyncio.create_task(urls2recipes(q, timeout)) for i in range(3)]
    await(asyncio.gather(*tasks))


def main(args: list[str], debug: bool = False, args_are_files: bool = True, verbosity: int = 1):
    misc.vlevel = verbosity
    file_setup(debug)

    known_urls: set[URL] = set()
    if os.path.isfile(known_urls_file):
        with open(known_urls_file, 'r') as file:
            for url in file.readlines(): known_urls.add(URL(url))

    unprocessed: list[str]
    if args:
        print("ARGS", args)
        if args_are_files:
            unprocessed = misc.read_files(*args)
        else:
            unprocessed = args
    else:
        unprocessed = misc.read_files(url_file)

    counts.strings = len(unprocessed)
    urls: set[URL] = process_urls(known_urls, unprocessed)
    counts.urls = len(urls)
    setup(counts, known_urls_name, recipes_name)
    asyncio.run(fetch(urls))
    print(counts)
