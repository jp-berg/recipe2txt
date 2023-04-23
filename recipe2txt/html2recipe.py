from enum import IntEnum
from typing import NewType, Final, Optional, NamedTuple, Any
from importlib_metadata import version
from recipe2txt.utils.markdown import *
from os import linesep
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
    scraper_version: str = '-1'


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


def int2status(t: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(t) != len(recipe_attributes):
        raise ValueError("Wanted length of " + str(len(recipe_attributes)) + ", got " + str(len(t)))
    assert(recipe_attributes[-2] == "status")
    try:
        status = RecipeStatus(int(t[-2]))
    except ValueError:
        status = RecipeStatus.NOT_INITIALIZED
    return t[:-2] + (status, t[-1])


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
        elif method == "ingredients": info = linesep.join(info)
        elif method == "nutrients": info = dict2str(info)
    if not info or info.isspace() or info == "None":
        dprint(1, "\t", method_name.capitalize(), "contains nothing", context=context)
        return NA
    return info


between_recipes: Final[str] = linesep * 5
head_sep: Final[str] = linesep * 2


def gen_status(infos: list[str]) -> RecipeStatus:
    if len(infos) > len(methods):
        raise ValueError("This function only analyzes attributes contained in html2recipe.methods."
                         " Expected " + str(len(methods)) + " elements, got " + str(len(infos)))
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


def _re2md(recipe: Recipe) -> str:
    title = esc(recipe.title)
    url = esc(recipe.url)
    host = italic(esc(recipe.host))
    if host == NA:
        host = None  # type: ignore

    escaped = [esc(item) for item in recipe.ingredients.split(linesep)]
    ingredients = unordered(*escaped)

    escaped = [esc(step) for step in recipe.instructions.split(linesep)]
    instructions = ordered(*escaped)

    md = "".join([
        header(title, 2, True),
        paragraph(),
        recipe.total_time + " min | " + recipe.yields,
        paragraph(),
        ingredients,
        EMPTY_COMMENT,
        instructions,
        paragraph(),
        italic("from:"), " ", link(url, host),
        paragraph()
    ])

    return md


def _re2txt(recipe: Recipe) -> str:
    txt = linesep.join([recipe.title,
                        head_sep,
                        recipe.total_time + " min | " + recipe.yields + linesep,
                        recipe.ingredients,
                        linesep * 2,
                        recipe.instructions.replace(linesep, linesep * 2),
                        linesep,
                        "from: " + recipe.url,
                        between_recipes])
    return txt


def recipe2out(recipe: Recipe, counts: Optional[Counts] = None, md: bool = False) -> Optional[str]:
    if recipe.status < RecipeStatus.INCOMPLETE_ESSENTIAL:
        dprint(1, "\t", "Nothing worthwhile could be extracted. Skipping...")
        return None
    if counts:
        if recipe.status < RecipeStatus.INCOMPLETE_ON_DISPLAY:
            counts.parsed_partially += 1
        else:
            counts.parsed_successfully += 1

    if md:
        return _re2md(recipe)
    else:
        return _re2txt(recipe)


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
