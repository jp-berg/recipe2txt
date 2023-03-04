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
from typing import Final, Callable, NewType, Tuple, Any

program_name:Final[str] = "RezeptZuTXT"
debug:Final[bool] = True
args_are_files:Final[bool] = True

#level 0 -> silent
#level 1 -> errors
#level 2 -> events
#level 3 -> setup

vlevel:int = -1
if debug:
    vlevel = 3
else:
    vlevel = 0

def dprint(level:int, *args:str, sep:str=' ', end:str='\n', file=None, flush:bool=False) -> None:
    if level >= vlevel:
        print(*args, sep=sep, end=end, file=file, flush=flush)
    

def ensure_existence_dir(*pathelements:str) -> str:
    path = os.path.join(*pathelements)
    if path.startswith("~"):
        path = os.path.expanduser(path)
    path = os.path.realpath(path)
    os.makedirs(path, exist_ok=True)
    return path

def ensure_existence_file(filename:str, *pathelements:str) -> str:
    path = os.path.join(ensure_existence_dir(*pathelements), filename)
    if not os.path.isfile(path):
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

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
URL = NewType('URL', str)
NA:Final[str] = "N/A"
def getInfo(name:str, func:Callable[[Parsed], Any], data):
    try:
        info = str(func(data))
        if not info or info.isspace():
            print("\t", name.capitalize(), "contains nothing")
            info = NA
        return info
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError):
        print("\t", "No", name, "found")
    except NotImplementedError:
        print("\t", name.capitalize(), "not implemented for this website")
    except Exception as e:
        print("\t", "Error while extracting", name)
        if(debug):
            traceback.print_exception(e)
            
    return NA

extraction_instructions:Final[list[Tuple[str, Callable[[Parsed], Any]]]] = [
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

def parsed2recipe(url:URL, parsed:Parsed) -> None:
    info = {}
    for instruction in extraction_instructions:
        info[instruction[0]] = getInfo(*instruction, parsed)
    
    if info["ingredients"] is NA and info["instructions"] is NA:
        print("\t", "Nothing worthwhile could be extracted. Skipping...")
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
    
    recipe2disk(url, recipe)

def html2recipe(url:URL, content:str) -> None:
    print("Processing", url)
    try:
        parsed:Parsed = Parsed(scrape_html(html = content, org_url = url))
    except (WebsiteNotImplementedError,
        NoSchemaFoundInWildMode):
        print("\t", "Unknown Website. Extraction not supported. Skipping...")
        return
    except AttributeError:
        print("\t", "Error while parsing website. Skipping...")
        return
    
    parsed2recipe(url, parsed)

async def urls2recipes(url_queue:asyncio.queues.Queue, timeout:aiohttp.client.ClientTimeout) -> None:
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not url_queue.empty():
            try:
                url = await url_queue.get()
                async with session.get(url) as response:
                    html = await response.text()
                
                html2recipe(url, html)
                
            except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                print("Issue with reaching ", url, ", skipping...")
                
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
                print("Already scraped:", url)
                continue
            if url in processed:
                print("Already queued:", url)
            else:
                processed.add(url)
        else:
            print("Not an URL:", string)
    return processed

def readfiles(*paths:str) -> list[str]:
    lines = []
    for path in paths:
        path = os.path.expanduser(path)
        path = os.path.realpath(path)
        if os.path.isfile(url_file):
            with open(url_file, 'r') as file:
                for line in file.readlines():
                    lines.append(line)
        else:
            print("Not a file:", path)
    return lines

async def fetch(urls:set[URL]) -> None:
    q:asyncio.queues.Queue = asyncio.Queue()
    for url in urls: await q.put(url)
    timeout = aiohttp.ClientTimeout(total = 10 * len(urls), connect = 1,
                                    sock_connect=None, sock_read = None)
    tasks = [asyncio.create_task(urls2recipes(q, timeout)) for i in range(3)]
    await(asyncio.gather(*tasks))

if __name__ == "__main__":
    
    if not os.path.isfile(recipe_file):
        print(recipe_file + "is not a file. Creating...")
        with open(recipe_file, 'w') as file:
            file.write("          REZEPTE\n")

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
    
    urls:set[URL] = processURLs(known_urls, unprocessed)
    asyncio.run(fetch(urls))

        

    
            
   

        
