import sys
import os.path
import validators
from os import getcwd, makedirs
import recipe_scrapers
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, ElementNotFoundInHtml
from xdg import xdg_cache_home, xdg_data_home
import aiohttp
import asyncio
import traceback
from typing import Final, Callable, NewType, Tuple, NamedTuple, Any

program_name:Final[str] = "RezeptZuTXT"
debug:Final[bool] = True
args_are_files:Final[bool] = True

#level 0 -> silent
#level 1 -> errors
#level 2 -> proceedings
#level 3 -> notice
#level 4 -> setup

vlevel:int = -1
if debug:
    vlevel = 3
else:
    vlevel = 0

Context = NewType('Context', Tuple[int, str])
nocontext:Final[Context] = Context((-1, ""))
def while_context(context:Context) -> Context:
    tmp = context[1]
    tmp = "While " + tmp[0].lower() + tmp[1:] + ":"
    return Context((context[0],  tmp))

def dprint(level:int, *args:str, sep:str=' ', end:str='\n', file:Any=None, flush:bool=False, context:Context=nocontext) -> Context:
    if level <= vlevel:
        if context[0] > vlevel:
            print(context[1], file=file, flush=flush, end=end)
        print(*args, sep=sep, end=end, file=file, flush=flush)
    return Context((level, sep.join(args)))
    
def ensure_existence_dir(*pathelements:str) -> str:
    path = os.path.join(*pathelements)
    if path.startswith("~"):
        path = os.path.expanduser(path)
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        dprint(4, "Creating directory:", path)
    os.makedirs(path, exist_ok=True)
    return path

def ensure_existence_file(filename:str, *pathelements:str) -> str:
    path = os.path.join(ensure_existence_dir(*pathelements), filename)
    if not os.path.isfile(path):
        dprint(4, "Creating file:", path)
        with open(path, 'w') as file:
            pass
    return path

known_urls_name:Final[str] = "knownURLs.txt"
recipes_name:Final[str] = "recipes.txt"
default_urls_name:Final[str] = "urls.txt"

workdir:str = os.path.expanduser(os.path.join("~", "Rezepte"))
default_data_directory:str = os.path.join(xdg_data_home(), program_name)
default_cache_directory:str = os.path.join(xdg_cache_home(), program_name)
if debug:
    workdir = os.path.join(getcwd(), "testfiles")
    default_data_directory = os.path.join(workdir, "data")
    default_cache_directory = os.path.join(workdir, "cache")

known_urls_file:Final[str] = ensure_existence_file(known_urls_name, default_data_directory)
url_file:Final[str] = ensure_existence_file(default_urls_name, workdir)
recipe_file:Final[str] = ensure_existence_file(recipes_name, workdir)

class Counts():
    def __init__(self) -> None:
        self.strings:int = 0
        self.urls:int = 0
        self.reached:int = 0
        self.parsed_successfully: int = 0
        self.parsed_partially:int = 0
    
    def __str__(self) -> str:
        return """
            \t [Absolute|Percentage of count above]
            Total number of strings: {}
            Identified as URLs: [{}|{:.2f}%]
            URLs reached: [{}|{:.2f}%]
            Recipes parsed partially: [{}|{:.2f}%]
            Recipes parsed fully: [{}|{:.2f}%]
            """.format(
                self.strings,
                self.urls, (self.urls/self.strings)*100,
                self.reached, (self.reached/self.urls)*100,
                self.parsed_partially, (self.parsed_partially/self.urls)*100,
                self.parsed_successfully, (self.parsed_successfully/self.urls)*100
                )
    
counts:Counts = Counts()

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
URL = NewType('URL', str)
NA:Final[str] = "N/A"
def getInfo(name:str, func:Callable[[Parsed], str|int|float], data:Parsed, context:Context) -> str:
    try:
        info = str(func(data))
        if not info or info.isspace():
            dprint(1, "\t", name.capitalize(), "contains nothing", context=context)
            info = NA
        return info
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError):
        dprint(1, "\t", "No", name, "found", context=context)
    except NotImplementedError:
        dprint(1, "\t", name.capitalize(), "not implemented for this website", context=context)
    except Exception as e:
        dprint(1, "\t", "Error while extracting", name, context=context)
        if(debug):
            traceback.print_exception(e)
            
    return NA

extraction_instructions:Final[list[Tuple[str, Callable[[Parsed], str|int|float]]]] = [
    ("title", lambda data:data.title()),
    ("total time", lambda data: data.total_time()),
    ("yields", lambda data: data.yields()),
    ("ingredients", lambda data: "\n".join(data.ingredients())),
    ("instructions", lambda data: "\n\n".join(data.instructions_list()))
]
between_recipes:Final[str] = "\n\n\n\n\n"
head_sep:Final[str] = "\n\n"

def recipe2disk(url:URL, recipe:str) -> None:
    with open(recipe_file, 'a') as file:
        file.write(recipe)

    with open(known_urls_file, 'a') as file:
        file.write(url)

def parsed2recipe(url:URL, parsed:Parsed, context:Context) -> None:
    info = {}
    for instruction in extraction_instructions:
        info[instruction[0]] = getInfo(*instruction, parsed, context=context)
        if info[instruction[0]] is NA: context = nocontext
    
    if info["ingredients"] is NA and info["instructions"] is NA:
        dprint(1, "\t", "Nothing worthwhile could be extracted. Skipping...", context=context)
        return
    else:
        recipe = "\n".join([info["title"],
                        head_sep,
                        info["total time"] + " min    " + info["yields"] + "\n",
                        info["ingredients"],
                        "\n\n",
                        info["instructions"],
                        "\n",
                        "from: " + url,
                        between_recipes])
    
        if NA in info.values():
            counts.parsed_partially +=1
        else:
            counts.parsed_successfully +=1
    
    recipe2disk(url, recipe)

def html2recipe(url:URL, content:str) -> None:
    context:Context = dprint(4, "Processing", url)
    context = while_context(context)
    try:
        parsed:Parsed = Parsed(scrape_html(html = content, org_url = url))
    except (WebsiteNotImplementedError,
        NoSchemaFoundInWildMode):
        dprint(1, "\t", "Unknown Website. Extraction not supported. Skipping...", context = context)
        return
    except AttributeError:
        dprint(1, "\t", "Error while parsing website. Skipping...", context = context)
        return
    
    parsed2recipe(url, parsed, context)

async def urls2recipes(url_queue:asyncio.queues.Queue, timeout:aiohttp.client.ClientTimeout) -> None:
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not url_queue.empty():
            try:
                url = await url_queue.get()
                context:Context = dprint(4, "Fetching", url)
                context = while_context(context)
                async with session.get(url) as response:
                    html = await response.text()
                
                counts.reached += 1
                html2recipe(url, html)
                
            except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                dprint(1, "\t", "Issue reaching website, skipping...", context=context)
                
def removeTracking(url:URL, *identifiers:str) -> URL:
    for i in identifiers:
        start_tracking_part = url.find(i)
        if(start_tracking_part > -1):
            tmp = url[:start_tracking_part]
            if validators.url(tmp):
                url = URL(tmp)
    return url

def processURLs(known_urls:set[URL], strings:list[str]) -> set[URL]:
    processed:set[URL] = set()
    for string in strings:
        string = string.replace(os.linesep, '')
        string.strip()
        if not string.startswith("http"):
            string = "http://"+string
        if validators.url(string):
            url:URL = URL(string)
            url = removeTracking(url, "/ref=", "?")
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

def readfiles(*paths:str) -> list[str]:
    lines = []
    for path in paths:
        path = os.path.expanduser(path)
        path = os.path.realpath(path)
        if os.path.isfile(url_file):
            dprint(4, "Reading", path)
            with open(url_file, 'r') as file:
                for line in file.readlines():
                    lines.append(line)
        else:
            dprint(1, "Not a file:", path)
    return lines

async def fetch(urls:set[URL]) -> None:
    q:asyncio.queues.Queue = asyncio.Queue()
    for url in urls: await q.put(url)
    timeout = aiohttp.ClientTimeout(total = 10 * len(urls), connect = 1,
                                    sock_connect=None, sock_read = None)
    tasks = [asyncio.create_task(urls2recipes(q, timeout)) for i in range(3)]
    await(asyncio.gather(*tasks))

if __name__ == "__main__":

    known_urls:set[URL] = set()
    if os.path.isfile(known_urls_file):
        with open(known_urls_file, 'r') as file:
            for url in file.readlines(): known_urls.add(URL(url)) 
    
    unprocessed:list[str] = []
    if 1 == len(sys.argv):
        unprocessed = readfiles(url_file)
    else:
        if args_are_files:
            unprocessed = readfiles(*sys.argv[1:])
        else:
            unprocessed = sys.argv[1:]
    
    counts.strings = len(unprocessed)
    urls:set[URL] = processURLs(known_urls, unprocessed)
    counts.urls = len(urls)
    asyncio.run(fetch(urls))
    print(counts)

        

    
            
   

        
