from enum import IntEnum
from typing import NewType, Final, Optional, NamedTuple, Any
from importlib_metadata import version
import traceback

from recipe2txt.utils.misc import dprint, Context, nocontext, URL, Counts, dict2str, while_context
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[str] = "N/A"
SCRAPER_VERSION: Final[str] = version('recipe_scrapers')


class RecipeStatus(IntEnum):
    NOT_INITIALIZED = -1
    UNREACHABLE = 0
    UNKNOWN = 1
    INCOMPLETE_ESSENTIAL = 2
    INCOMPLETE_ON_DISPLAY = 3
    COMPLETE_ON_DISPLAY = 4
    COMPLETE = 5


class Recipe(NamedTuple):
    ingredients: str = NA
    instructions: str = NA
    title: str = NA
    total_time: str = NA
    yields: str = NA
    host: str = NA
    image: str = NA
    nutrients: str = NA
    url: URL = URL("https://notinitialized.no")
    status: RecipeStatus = RecipeStatus.NOT_INITIALIZED
    scraper_version: str = '0.0'


uninit_recipe: Final[Recipe] = Recipe()


def none2na(t: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(t) > len(recipe_attributes):
        raise ValueError("Expected a Recipe-based tuple, but got something longer")
    if None in t:
        tmp = list(t)
        t = tuple([tmp[i] if tmp[i] else getattr(uninit_recipe, recipe_attributes[i]) for i in range(len(tmp))])
    return t


essential: Final[list[str]] = [
    "ingredients",
    "instructions"
]
on_display: Final[list[str]] = essential + [
    "title",
    "total_time",
    "yields",
]
methods: Final[list[str]] = on_display + [
    "host",
    "image",
    "nutrients"
]
recipe_attributes: Final[list[str]] = methods + [
    "url",
    "status",
    "scraper_version"
]


def _get_info(method: str, data: Parsed, context: Context) -> str:
    error_level = 1
    if method not in on_display: error_level = 2

    method_name = method.replace("_", " ")
    try:
        info = getattr(data, method)()
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError):
        dprint(error_level, "\t", "No", method_name, "found", context=context)
        return NA
    except NotImplementedError:
        dprint(error_level, "\t", method_name.capitalize(), "not implemented for this website", context=context)
        return NA
    except Exception as e:
        dprint(error_level, "\t", "Extraction error", method_name, context=context)
        exception_trace = "\t" + "\t".join(traceback.format_exception(e))
        dprint(4, exception_trace)
        return NA

    if info:
        if method == "total_time":
            if info == 0:
                info = None
            else:
                info = str(info)
        elif method == "ingredients": info = "\n".join(info)
        elif method == "nutrients": info = dict2str(info)
    if not info or info.isspace() or info == "None":
        dprint(1, "\t", method_name.capitalize(), "contains nothing", context=context)
        return NA
    return info


between_recipes: Final[str] = "\n\n\n\n\n"
head_sep: Final[str] = "\n\n"


def gen_status(infos: list[str]) -> RecipeStatus:
    for i in range(len(essential)):
        if infos[i] == NA:
            return RecipeStatus.INCOMPLETE_ESSENTIAL
    for i in range(len(essential), len(on_display)):
        if infos[i] == NA:
            return RecipeStatus.INCOMPLETE_ON_DISPLAY
    for i in range(len(on_display), len(methods)):
        if infos[i] == NA:
            return RecipeStatus.COMPLETE_ON_DISPLAY
    return RecipeStatus.COMPLETE


def parsed2recipe(url: URL, parsed: Parsed) -> Recipe:
    context = dprint(4, "Parsing", url)
    context = while_context(context)
    infos = []
    for method in methods:
        infos.append(_get_info(method, parsed, context))
        if infos[-1] is NA: context = nocontext
    status = gen_status(infos)
    recipe = Recipe(url=url, status=status, scraper_version=SCRAPER_VERSION,
                    ingredients=infos[0], instructions=infos[1],
                    title=infos[2], total_time=infos[3], yields=infos[4],
                    host=infos[5], image=infos[6], nutrients=infos[7])
    return recipe


def recipe2txt(recipe: Recipe, counts: Optional[Counts] = None) -> Optional[str]:
    if recipe.status is RecipeStatus.INCOMPLETE_ESSENTIAL:
        dprint(1, "\t", "Nothing worthwhile could be extracted. Skipping...")
        return None
    else:
        txt = "\n".join([recipe.title,
                         head_sep,
                         recipe.total_time + " min    " + recipe.yields + "\n",
                         recipe.ingredients,
                         "\n\n",
                         recipe.instructions.replace("\n", "\n"),
                         "\n",
                         "from: " + recipe.url,
                         between_recipes])
        if counts:
            if NA in [recipe.title, recipe.total_time, recipe.yields, recipe.ingredients, recipe.instructions]:
                counts.parsed_partially += 1
            else:
                counts.parsed_successfully += 1
        return txt


def html2parsed(url: URL, content: str) -> Optional[Parsed]:
    try:
        parsed: Parsed = Parsed(recipe_scrapers.scrape_html(html=content, org_url=url))
    except (WebsiteNotImplementedError,
            NoSchemaFoundInWildMode):
        dprint(1, "Unknown Website. Extraction not supported for", url)
        return None
    except AttributeError:
        dprint(1, "Error while parsing", url)
        return None

    return parsed
