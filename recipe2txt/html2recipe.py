import logging
from enum import IntEnum
from typing import NewType, Final, Optional, NamedTuple, Any
from importlib_metadata import version
from recipe2txt.utils.markdown import *
from os import linesep
import traceback

from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM
from recipe2txt.utils.misc import URL, Counts, dict2str
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

logger = get_logger(__name__)

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
    assert (recipe_attributes[-2] == "status")
    try:
        status = RecipeStatus(int(t[-2]))
    except ValueError:
        status = RecipeStatus.NOT_INITIALIZED
    return t[:-2] + (status, t[-1])


def _get_info(method: str, data: Parsed) -> str:
    log = logger.error if method not in on_display else logger.warning

    method_name = method.replace("_", " ")
    try:
        info = getattr(data, method)()
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError, KeyError):
        log(f"No {method_name} found")
        return NA
    except NotImplementedError:
        log(f"{method_name.capitalize()} not implemented for this website")
        return NA
    except Exception as e:
        log(f"Extraction error: {method_name}")
        if logger.isEnabledFor(logging.DEBUG):
            exception_trace = "\t" + "\t".join(traceback.format_exception(e))
            logger.debug(exception_trace)
        return NA

    if isinstance(info, (int, float)):
        info = None if info == 0 else str(info)

    if info:
        if method == "ingredients":
            if not isinstance(info, str):
                info = linesep.join(info)
        elif method == "nutrients":
            info = dict2str(info)
        elif method == "instructions":
            if isinstance(info, str):
                info = info.replace(linesep*2, linesep)
            elif isinstance(info, list):
                info = linesep.join(info)
    if not info or info.isspace() or info == "None":
        logger.error(f"{method_name.capitalize()} contains nothing")
        return NA
    return str(info)


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
    with QCM(logger, logger.info, f"Parsing {url}"):
        infos = []
        for method in methods:
            infos.append(_get_info(method, parsed))
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
        logger.error("Nothing worthwhile could be extracted. Skipping...")
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
        logger.error(f"Unknown Website. Extraction not supported for {url}")
        return None
    except AttributeError:
        logger.error(f"Error while parsing {url}")
        return None

    return parsed
