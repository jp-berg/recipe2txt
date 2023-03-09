from typing import NewType, Final, Callable, Tuple
import traceback

from .utils.misc import dprint, Context, nocontext, while_context, URL, Counts
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[str] = "N/A"

_counts: Counts
_known_urls_file: str
_recipes_file: str


def setup(counts: Counts, known_urls_file: str, recipes_file: str) -> None:
    global _counts
    _counts = counts
    global _known_urls_file
    _known_urls_file = known_urls_file
    global _recipes_file
    _recipes_file = recipes_file


def _get_info(name: str, func: Callable[[Parsed], str | int | float], data: Parsed, context: Context, debug:bool = False) -> str:
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
        dprint(1, "\t", "Extraction error", name, context=context)
        if debug:
            traceback.print_exception(e)

    return NA


extraction_instructions: Final[list[Tuple[str, Callable[[Parsed], str | int | float]]]] = [
    ("title", lambda data: data.title()),
    ("total time", lambda data: data.total_time()),
    ("yields", lambda data: data.yields()),
    ("ingredients", lambda data: "\n".join(data.ingredients())),
    ("instructions", lambda data: "\n\n".join(data.instructions_list()))
]
between_recipes: Final[str] = "\n\n\n\n\n"
head_sep: Final[str] = "\n\n"


def recipe2disk(url: URL, recipe: str) -> None:
    with open(_recipes_file, 'a') as file:
        file.write(recipe)

    with open(_known_urls_file, 'a') as file:
        file.write(url)


def parsed2recipe(url: URL, parsed: Parsed, context: Context, debug: bool = False) -> None:
    info = {}
    for instruction in extraction_instructions:
        info[instruction[0]] = _get_info(*instruction, parsed, context=context, debug=debug)
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
            _counts.parsed_partially += 1
        else:
            _counts.parsed_successfully += 1

    recipe2disk(url, recipe)


def html2recipe(url: URL, content: str) -> None:
    context: Context = dprint(4, "Processing", url)
    context = while_context(context)
    try:
        parsed: Parsed = Parsed(recipe_scrapers.scrape_html(html=content, org_url=url))
    except (WebsiteNotImplementedError,
            NoSchemaFoundInWildMode):
        dprint(1, "\t", "Unknown Website. Extraction not supported. Skipping...", context=context)
        return
    except AttributeError:
        dprint(1, "\t", "Error while parsing website. Skipping...", context=context)
        return

    parsed2recipe(url, parsed, context)
