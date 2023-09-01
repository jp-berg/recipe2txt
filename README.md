# Introduction

`recipe2txt` is a CLI-program that you can feed your urls of recipes and it spits out formatted cookbooks containing those recipes. Highlights include:

* asynchronous fetching of recipes
* formatted output either as txt- or markdown-file
* local caching of recipes

The program is a wrapper for the [recipe-scrapers](https://github.com/hhursev/recipe-scrapers)-library. Please visit their README.md if you would like to know which sites are supported.

# WARNING

THIS SOFTWARE IS AT AN EARLY DEVELOPEMENT STAGE.

BE CAREFUL SETTING THE `--output`-FLAG, ANY EXISTING FILES WITH THE SAME NAME WILL BE OVERWRITTEN.

TESTED ONLY ON KUBUNTU 23.04.

# Usage

Install with `pip install recipe2txt`. You can either use `recipe2txt` or `re2txt` to run the program.

```
usage: recipes2txt [-h] [-u URL [URL ...]] [-f FILE [FILE ...]] [-o OUTPUT] [-v {debug,info,warning,error,critical}]
                   [-con CONNECTIONS] [-ia] [-c {only,new,default}] [-d] [-t TIMEOUT] [-md] [-ua USER_AGENT]
                   [-sa | -erase | -do DEFAULT_OUTPUT_FILE]

Scrapes URLs of recipes into text files

options:
  -h, --help            show this help message and exit
  -u URL [URL ...], --url URL [URL ...]
                        URLs whose recipes should be added to the recipe-file
  -f FILE [FILE ...], --file FILE [FILE ...]
                        Text-files containing URLs (one per line) whose recipes should be added to the recipe-file
  -o OUTPUT, --output OUTPUT
                        Specifies an output file. If empty or not specified recipes will either be written into the
                        current working directory or into the default output file (if set). THIS WILL OVERWRITE ANY
                        EXISTING FILE WITH THE SAME NAME.
  -v {debug,info,warning,error,critical}, --verbosity {debug,info,warning,error,critical}
                        Sets the 'chattiness' of the program (default 'critical')
  -con CONNECTIONS, --connections CONNECTIONS
                        Sets the number of simultaneous connections (default: 4).
  -ia, --ignore-added   [NI]Writes recipe to file regardless if it has already been added
  -c {only,new,default}, --cache {only,new,default}
                        Controls how the program should handle its cache: With 'only' no new data will be downloaded,
                        the recipes will be generated from data that has been downloaded previously. If a recipe is
                        not in the cache, it will not be written into the final output. 'new' will make the program
                        ignore any saved data and download the requested recipes even if they have already been
                        downloaded. Old data will be replaced by the new version, if it is available. The 'default'
                        will fetch and merge missing data with the data already saved, only inserting new data into
                        the cache where there was none previously.
  -d, --debug           Activates debug-mode: Changes the directory for application data
  -t TIMEOUT, --timeout TIMEOUT
                        Sets the number of seconds the program waits for an individual website to respond , eg. sets
                        the connect-value of aiohttp.ClientTimeout (default: 10.0 seconds)
  -md, --markdown       Generates markdown-output instead of '.txt'
  -ua USER_AGENT, --user-agent USER_AGENT
                        Sets the user-agent to be used for the requests. (default: 'Mozilla/5.0 (Windows NT 10.0;
                        Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0')
  -sa, --show-appdata   Shows data- and cache-files used by this program
  -erase, --erase-appdata
                        Erases all data- and cache-files used by this program
  -do DEFAULT_OUTPUT_FILE, --default-output-file DEFAULT_OUTPUT_FILE
                        Sets a file where recipes should be written to if no output-file is explicitly passed via '-o'
                        or '--output'. Pass 'RESET' to reset the default output to the current working directory. Does
                        not work in debug mode (default-output-file is automatically set by
                        'tests/testfiles/default_output_location.txt').

[NI] = 'Not implemented (yet)'
```

# Examples

```bash
recipe2txt -u www.example-url.com/tastyrecipe www.other-examle-url.org/deliciousmeal -o ~/Documents/great-recipes.txt
```

# Developement

## Tools

### nox

This project (ab-)uses [nox](https://github.com/wntrblm/nox) as test-(and task-)runner. Install nox from PyPi.org (e.g. `pipx install nox`). Use `nox --list` to get an overview over the different routines the [noxfile](noxfile.py) provides. For example to create the developement enviroment use `nox -s dev`.

### mypy

This project uses [mypy](https://github.com/python/mypy) for type checking. The [configuration file](pyproject.toml) contains all relevant settings, so a simple call to `mypy` from the current directory should be sufficient to typecheck the project.
