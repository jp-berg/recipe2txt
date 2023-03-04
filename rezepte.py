import sys
import os.path
import validators
from os import getcwd, makedirs
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, ElementNotFoundInHtml
from xdg import xdg_cache_home, xdg_data_home
import aiohttp
import asyncio
import traceback

program_name = "RezeptZuTXT"
debug = True
args_are_files = True

def ensure_existence_dir(*pathelements):
    path = os.path.join(*pathelements)
    if path.startswith("~"):
        path = os.path.expanduser(path)
    path = os.path.realpath(path)
    os.makedirs(path, exist_ok=True)
    return path

def ensure_existence_file(filename, *pathelements):
    path = os.path.join(ensure_existence_dir(*pathelements), filename)
    if not os.path.isfile(path):
        with open(path, 'w') as file:
            pass
    return path

known_urls_name = "knownURLs.txt"
recipes_name = "recipes.txt"
default_urls_name = "urls.txt"

if debug:
    workdir = os.path.join(getcwd(), "testfiles")
    default_data_directory = os.path.join(workdir, "data")
    default_cache_directory = os.path.join(workdir, "cache")
else:
    workdir = os.path.expanduser(os.path.join("~", "Rezepte"))
    default_data_directory = os.path.join(xdg_data_home(), program_name)
    default_cache_directory = os.path.join(xdg_cache_home(), program_name)

known_urls_file = ensure_existence_file(known_urls_name, default_data_directory)
url_file = ensure_existence_file(default_urls_name, workdir)
recipe_file = ensure_existence_file(recipes_name, workdir)

NA = "N/A"
def getInfo(name, func, data):
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

extraction_instructions = [
    ("title", lambda data:data.title()),
    ("total time", lambda data: data.total_time()),
    ("yields", lambda data: data.yields()),
    ("ingredients", lambda data: "\n".join(data.ingredients())),
    ("instructions", lambda data: "\n\n".join(data.instructions_list()))
]
between_recipes = "\n\n\n\n\n"
head_sep = "\n\n"

def recipe2disk(url, recipe):
    with open(recipe_file, 'a') as file:
        file.write(recipe)

    with open(known_urls_file, 'a') as file:
        file.write(url)

def parsed2recipe(url, scraped):
    info = {}
    for instruction in extraction_instructions:
        info[instruction[0]] = getInfo(*instruction, scraped)
    
    if info["ingredients"] is NA and info["instructions"] is NA:
        print("\t", "Nothing worthwhile could be extracted. Skipping...")
        return None
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
    
    return recipe2disk(url, recipe)

def html2recipe(url, content):
    print("Processing", url)
    try:
        parsed = scrape_html(html = content, org_url = url)
    except (WebsiteNotImplementedError,
        NoSchemaFoundInWildMode):
        print("\t", "Unknown Website. Extraction not supported. Skipping...")
        return None
    except AttributeError:
        print("\t", "Error while parsing website. Skipping...")
        return None
    
    return parsed2recipe(url, parsed)

async def urls2recipes(url_queue, timeout):
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not url_queue.empty():
            try:
                url = await url_queue.get()
                async with session.get(url) as response:
                    html = await response.text()
                
                recipe = html2recipe(url, html)
                
            except (aiohttp.client_exceptions.TooManyRedirects, asyncio.TimeoutError):
                network_timer.end_multi(timer_id)
                print("Issue with reaching ", url, ", skipping...")
                
def removeTracking(url, *identifiers):
    for i in identifiers:
        start_tracking_part = url.find(i)
        if(start_tracking_part > -1):
            tmp = url[:start_tracking_part]
            if validators.url(tmp):
                url = tmp
    return url

def processURLs(known_urls, urls):
    processed = set()
    for url in urls:
        url = url.replace(os.linesep, '')
        url.strip()
        if not url.startswith("http"):
            url = "http://"+url
        if validators.url(url):
            url = removeTracking(url, "/ref=", "?")
            if url in known_urls:
                print("Already scraped:", url)
                continue
            if url in processed:
                print("Already queued:", url)
            else:
                processed.add(url)
        else:
            print("Not an URL:", url)
    return processed

def readfiles(*paths):
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

async def fetch(urls):
    q = asyncio.Queue()
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

    if os.path.isfile(known_urls_file):
        with open(known_urls_file, 'r') as file:
            known_urls = set(file.readlines())
    else:
        known_urls = set()
    
    if 1 == len(sys.argv):
        unprocessed = readfiles(url_file)
    else:
        if args_are_files:
            unprocessed = readfiles(sys.argv[1:])
        else:
            unprocessed = sys.argv[1:]
    
    urls = processURLs(known_urls, unprocessed)
    asyncio.run(fetch(urls))

        

    
            
   

        
