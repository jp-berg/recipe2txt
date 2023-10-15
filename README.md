# Introduction

`recipe2txt` is a CLI-program that you can feed your urls of recipes and it spits out formatted cookbooks containing those recipes. Highlights include:

* asynchronous fetching of recipes
* formatted output either as txt- or markdown-file
* local caching of recipes

The program is a wrapper for the [recipe-scrapers](https://github.com/hhursev/recipe-scrapers)-library. Please visit their README.md if you would like to know which websites are supported.

# WARNING

THIS SOFTWARE IS AT AN EARLY DEVELOPEMENT STAGE.

BE CAREFUL SETTING THE `--output`-FLAG, ANY EXISTING FILES WITH THE SAME NAME WILL BE OVERWRITTEN.

TESTED ONLY ON KUBUNTU 23.04.

# Usage

Install with `pip install recipe2txt`. You can either use `recipe2txt` or `re2txt` to run the program.

```
usage: recipes2txt [-h] [--file [FILE ...]] [--output OUTPUT] [--verbosity {debug,info,warning,error,critical}]
                   [--connections CONNECTIONS] [--cache {only,new,default}] [--debug] [--timeout TIMEOUT]
                   [--markdown] [--user-agent USER_AGENT] [--erase-appdata ERASE_APPDATA]
                   [url ...]

Scrapes URLs of recipes into text files

positional arguments:
  url                   URLs whose recipes should be added to the recipe-file (default: '[]')

options:
  -h, --help            show this help message and exit
  --file [FILE ...], -f [FILE ...]
                        Text-files containing URLs whose recipes should be added to the recipe-file (default:
                        '[]')
  --output OUTPUT, -o OUTPUT
                        Specifies an output file. THIS WILL OVERWRITE ANY EXISTING FILE WITH THE SAME NAME.
                        (default: '/home/pc/sciebo/Dokumente/Programming/recipe2txt/recipes')
  --verbosity {debug,info,warning,error,critical}, -v {debug,info,warning,error,critical}
                        Sets the 'chattiness' of the program (default: 'critical')
  --connections CONNECTIONS, -con CONNECTIONS
                        Sets the number of simultaneous connections (default: '4')
  --cache {only,new,default}, -c {only,new,default}
                        Controls how the program should handle its cache: With 'only' no new data will be
                        downloaded, the recipes will be generated from data that has been downloaded previously.
                        If a recipe is not in the cache, it will not be written into the final output. 'new' will
                        make the program ignore any saved data and download the requested recipes even if they
                        have already been downloaded. Old data will be replaced by the new version, if it is
                        available. The 'default' will fetch and merge missing data with the data already saved,
                        only inserting new data into the cache where there was none previously. (default:
                        'default')
  --debug, -d           Activates debug-mode: Changes the directory for application data (default: 'False')
  --timeout TIMEOUT, -t TIMEOUT
                        Sets the number of seconds the program waits for an individual website to respond, eg.
                        sets the connect-value of aiohttp.ClientTimeout. (default: '10.0')
  --markdown, -m        Generates markdown-output instead of '.txt' (default: 'False')
  --user-agent USER_AGENT, -ua USER_AGENT
                        Sets the user-agent to be used for the requests. (default: 'Mozilla/5.0 (Windows NT 10.0;
                        Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0')
  --erase-appdata ERASE_APPDATA
                        Erases all data- and cache-files
```

When first run the program will generate the config-file `recipe2txt.toml` (use `recipe2txt --help` to locate it).
Every option listed above has a pendant in that file. Uncomment [^1] the line and change the value after the `=`-
sign to change the value this program uses when the option is not specified via the CLI-interface.

[^1]: Remove the leading `#`

# Examples

```bash
recipe2txt www.example-url.com/tastyrecipe www.other-examle-url.org/deliciousmeal -o ~/Documents/great-recipes.txt
```

# Developement

## Tools

### nox

This project (ab-)uses [nox](https://github.com/wntrblm/nox) as test-(and task-)runner. Install nox from PyPi.org (e.g. `pipx install nox`). Use `nox --list` to get an overview over the different routines the [noxfile](noxfile.py) provides. For example to create the developement enviroment use `nox -s dev`.

### mypy

This project uses [mypy](https://github.com/python/mypy) for type checking. The [configuration file](pyproject.toml) contains all relevant settings, so a simple call to `mypy` from the current directory should be sufficient to typecheck the project.
