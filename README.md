# Introduction

`recipe2txt` is a CLI-program that you can feed your urls of recipes and it spits out formatted cookbooks containing those recipes. Highlights include:

* asynchronous fetching of recipes
* formatted output either as txt- or markdown-file
* local caching of recipes
* custom recipe formatting via [jinja](https://jinja.palletsprojects.com)

The program is a wrapper for the [recipe-scrapers](https://github.com/hhursev/recipe-scrapers)-library. Please visit their README.md if you would like to know which websites are supported.

# WARNING

THIS SOFTWARE IS AT AN EARLY DEVELOPMENT STAGE.

BE CAREFUL SETTING THE `--output`-FLAG, ANY EXISTING FILES WITH THE SAME NAME WILL BE OVERWRITTEN.

TESTED ONLY ON KUBUNTU.

# Usage

Install with `pip install recipe2txt`. You can either use `recipe2txt` or `re2txt` to run the program.

```
usage: recipes2txt [-h] [--file [FILE ...]] [--output OUTPUT] [--verbosity {debug,info,warning,error,critical}]
                   [--connections CONNECTIONS] [--cache {only,new,default}] [--debug] [--timeout TIMEOUT]
                   [--output-format {md,txt}] [--user-agent USER_AGENT] [--erase-appdata] [--version]
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
                        sets the connect-value of aiohttp.ClientTimeout (default: '10.0')
  --output-format {md,txt}, -of {md,txt}
                        Sets the format for the output-file. The value defines which .jinja-template will be used
                        to format the file. The templates are available under
                        '/home/pc/.config/recipes2txt/templates'. (default: 'txt')
  --user-agent USER_AGENT, -ua USER_AGENT
                        Sets the user-agent to be used for the requests. (default: 'Mozilla/5.0 (Windows NT 10.0;
                        Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0')
  --erase-appdata       Erases all data- and cache-files (e.g. the files listed below) (default: 'False')
  --version             Displays the version number (SemVer) (default: 'False')
```

## Configuration

When first run the program will generate the config-file `recipe2txt.toml` (use `recipe2txt --help` to locate it).
Every option listed above has a pendant in that file. Uncomment [^1] the line and change the value after the `=`-
sign to change the value this program uses when the option is not specified via the CLI-interface.

[^1]: Remove the leading `#`

### Jinja-Templates

When first run the program will create the config-folder `templates`. Here reside the jinja-templates used for
formatting recipes. Simply modify the existing templates or create your own.

#### Creating your own templates

Jinja-templates are provided with:

* recipes: a Python-list of `Recipe`-objects, each containing
  * ingredients: the ingredients, separated by newlines
  * instructions: the instructions, separated by newlines
  * title
  * total_time
  * yields: how many people can eat this recipe
  * host: which website the recipe is hosted on
  * image: an url to an accompanying image
  * nutrients: Python-dictionary of the nutrients
  * url: the url to the recipe
  * status: an integer representing the completeness of the recipe
  * scraper_version: the version of the recipe-scrapers-library used to scrape this recipe
* The NA-constant
  * used to represent values in the `Recipe`-object that are not available
* The functions of the `recipe2txt.utils.markdown`-module

#### Using your own templates

All `.jinja`-files in the folder are collected and their extentions are stripped to create an identifier for that template.
E.g.: The template is named `rst.jinja` => specify `--output-format rst` to use the template.


# Examples

```bash
recipe2txt www.example-url.com/tastyrecipe www.other-examle-url.org/deliciousmeal -o ~/Documents/great-recipes.txt
```

# Development

## Versioning

This project tries to adhere to (Semantic Versioning)[https://semver.org/]. While using '0.'-version-numbers, '0.N+1'-increases mean API changes (breaking and non-breaking), while '0.N.M+1' means no noticable API-changes.

## Tools

### nox

This project (ab-)uses [nox](https://github.com/wntrblm/nox) as test-(and task-)runner. Install nox from PyPi.org (e.g. `pipx install nox`). Use `nox --list` to get an overview over the different routines the [noxfile](noxfile.py) provides. For example to create the developement enviroment use `nox -s dev`.

### mypy

This project uses [mypy](https://github.com/python/mypy) for type checking. The [configuration file](pyproject.toml) contains all relevant settings, so a simple call to `mypy` from the current directory should be sufficient to typecheck the project.

### black

The project uses [black](https://github.com/psf/black) for code formatting.

## Testing

The project uses Python unittest for unit- and integration testing. The tests are defined in the `test.test_...`-modules. The `test/testfiles`-folder contains permanent and non-permanent testfiles.

Permanent testfiles are used to validate that the output of the program does not drift unintentionally. A reimplementation of the '.jinja'-templates in Python ensures their validity for example. Some of those files are derived from Material not licensed under the GPL3-License. Please see `test/testfiles/permanent/LICENSE` for more information.

Non-permanent testfiles are temporary files and folders generated during testing. They are written into the folder `test/testfiles/tmp_testfiles_re2txt`. Outside of unittest-runs this folder should never appear.

Sytem testing is facilitated via the `test.test4recipe2txt`-module. The module is used to create and run different CLI-parameter configurations of the program. At the end of a testrun it saves all files generated during the run and the initial parameters into a zip-file in `test/reports_test4recipe2txt` for later review. For each run the program uses the `test/reports_test4recipe2txt`-file to optain the urls to use in the testrun. To stress all websites equally and to avoid testing the same websites over and over the urls the file represents a queue, where the urls to use next are at the top and recently used urls will be moved to the bottom. If the file does not exist it will be generated from `test/testfiles/permanent/all_urls.txt`.
