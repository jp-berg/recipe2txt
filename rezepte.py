import sys
import os.path
import validators
from os import getcwd, makedirs
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, ElementNotFoundInHtml
from xdg import xdg_cache_home, xdg_data_home
import requests

program_name = "RezeptZuTXT"

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
    


debug = True

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

between_recipes = "\n\n\n\n\n"
head_sep = "\n\n"

def extract_info(scraped):
    count = 0
    
    try:
        name = scraped.title()
    except (TypeError, AttributeError):
        print("No title found")
        name = NA
        count += 1
    
    try:
        total_time = str(scraped.total_time())
    except (SchemaOrgException, ElementNotFoundInHtml, AttributeError):
        print("No time found")
        total_time = NA
        count += 1
    except NotImplementedError:
        print("Website not fully supported")
        total_time = NA
        count += 1
    
    try:
        yields = scraped.yields()
    except Exception:
        print("No servings amount found")
        yields = NA
        count += 1
    
    try:
        ingredients = "\n".join(scraped.ingredients())
    except AttributeError:
        print("No ingredient list found")
        ingredients = NA
        count += 1
        
    try:
        instructions = "\n\n".join(scraped.instructions_list())
    except AttributeError:
        print("No instructions found")
        instructions = NA
        count += 1
    
    if count == 5:
        print("Nothing could be extracted. Skipping...")
        recipe = None
    else:
        recipe = "\n".join([name,
                        head_sep,
                        total_time + "min    " + yields + "\n",
                        ingredients,
                        "\n\n",
                        instructions,
                        "\n",
                        "von: " + url,
                        between_recipes])
    return recipe

def url2recipe(url):
    start_tracking_part = url.find("?")
    if(start_tracking_part > -1):
        url = url[:start_tracking_part]
        
    print(url[:-1])

    try:
        html = requests.get(url, timeout = 1).content
    except (requests.exceptions.Timeout, requests.exceptions.TooManyRedirects, requests.exceptions.ConnectionError):
        print("Issue with reaching website. Skipping...")
        return None
    
    try:
        s = scrape_html(html = html, org_url = url)
    except (WebsiteNotImplementedError,
           NoSchemaFoundInWildMode):
        print("Unknown Website. Extraction not supported. Skipping...")
        return None
    
    return extract_info(s)

to_scrape = set()
def addURL(url):
    if validators.url(url):
        if url in known_urls:
            print("Already scraped:", url)
        elif url in to_scrape:
            print("Already queued:", url)
        else:
            to_scrape.add(url)
        return True
    else:
        return False

def urls2queue(uri):
    if addURL(uri):
        return

    url_file = os.path.expanduser(uri)
    if os.path.isfile(url_file):
        with open(url_file, 'r') as file:
            for url in file.readlines():
                if not addURL(url):
                    print("Not an URL:", url)
        return

    print("Not an URL or a file:", uri)
        
        

if __name__ == "__main__":
        
    if not os.path.isfile(recipe_file):
        print(recipe_file + " is not a file. Creating...")
        with open(recipe_file, 'w') as file:
            file.write("          REZEPTE\n")

    
    if os.path.isfile(known_urls_file):
        with open(known_urls_file, 'r') as file:
            known_urls = file.readlines()

        known_urls = set(known_urls)
    else:
        known_urls = set()
    
    if 1 == len(sys.argv):
        urls2queue(url_file)
    else:
        for uri in sys.argv[1:]:
            urls2queue(uri)
        
    for url in to_scrape:
        recipe = url2recipe(url)
        if recipe:
            with open(recipe_file, 'a') as file:
                file.write(recipe)

            known_urls.add(url)
            with open(known_urls_file, 'a') as file:
                file.write(url)
        print()

        

    
            
   

        
