import sys
import os.path
from recipe_scrapers import scrape_me
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode
import argparse
from xdg import xdg_data_home, xdg_cache_home, xdg_state_home


program_name = "RezeptZuTXT"
#import requests.exceptions.ConnectionError
default_url_file = ["~", "test.txt"]
#default_recipe_file = "~/sciebo/Documente/Notizen/Rezepte.txt"
default_recipe_file = ["~", "sciebo", "Dokumente", "Notizen", "Rezepte.txt"]
default_data_directory = os.path.join(xdg_data_home(), program_name)
default_cache_directory = os.path.join(xdg_cache_home(), program_name)
default_state_directory = os.path.join(xdg_state_home(), program_name)

known_urls_file = os.path.expanduser(os.path.join(*default_data_directory))



parser = argparse.ArgumentParser(description='Scrape recipes into a textfile',
                                 prog = program_name)
parser.add_argument('-s', '-source', default = 'u',
                    choices = ['u', 'f'], required = True,
                    type = str, nargs='+',
                    usage="specifies, wether the passed argument are urls or files containing urls")
parser.add_argument("-v", "--verbosity", action="count", default=0)




between_recipes = "\n\n\n\n\n"
head_sep = "\n\n"
def url2recipe(url):
    start_tracking_part = url.find("?")
    if(start_tracking_part > -1):
        url = url[:start_tracking_part]
        
    print(url)

    if url in known_urls:
        print("Recipe already scraped. Skipping...")
        continue

    try:
        s = scrape_me(url)
    except WebsiteNotImplementedError:
        print("Unknown Website. Extraction not supported. Skipping...")
        continue

        
    name = s.title()
    total_time = str(s.total_time())
    yields = s.yields()
    ingredients = "\n".join(s.ingredients())
    instructions = "\n\n".join(s.instructions_list())

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
        

        

if __name__ == "__main__":

    nargs = len(sys.argv)
    if nargs > 3:
        sys.exit("Wrong number of arguments (expected one file)...")
    

    if nargs == 1:
        url_file = os.path.expanduser(os.path.join(*default_url_file))
    else if:
        sys.argv[1].toLo
        url_file = os.path.expanduser(sys.argv[1])

    if not os.path.isfile(url_file):
        recipe = url2recipe(url_file)

    if nargs > 2:
        recipe_file = os.path.expanduser(sys.argv[2])
    else:
        recipe_file = os.path.expanduser(os.path.join(*default_recipe_file))

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
    
    with open(url_file, 'r') as file:
        urls = file.readlines()

    
    
    for url in urls:
        recipe = url2recipe(url)

        with open(recipe_file, 'a') as file:
            file.write(recipe)

        known_urls.add(url)
        with open(known_urls_file, 'a') as file:
            file.write(url)

        

    
            
   

        
