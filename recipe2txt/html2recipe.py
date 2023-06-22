import logging
from enum import IntEnum
from typing import NewType, Final, Optional, NamedTuple, Any
from sys import version_info

if version_info >= (3, 11):
    from typing import LiteralString
else:
    from typing_extensions import LiteralString
from os import linesep
import traceback
from importlib_metadata import version
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml
from recipe2txt.utils.markdown import *
from recipe2txt.utils.ContextLogger import get_logger, QueueContextManager as QCM
from recipe2txt.utils.misc import URL, Counts, dict2str

logger = get_logger(__name__)

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[LiteralString] = "N/A"
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


UNINIT_RECIPE: Final[Recipe] = Recipe()


def none2na(t: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(t) > len(RECIPE_ATTRIBUTES):
        raise ValueError(f"Expected a Recipe-based tuple (length {len(t)},"
                         f" but got something longer (length {len(RECIPE_ATTRIBUTES)})")
    if None in t:
        tmp = list(t)
        t = tuple([tmp[i] if tmp[i] else getattr(UNINIT_RECIPE, RECIPE_ATTRIBUTES[i]) for i in range(len(tmp))])
    return t


ESSENTIAL: Final[list[LiteralString]] = [
    "ingredients",
    "instructions"
]
ON_DISPLAY: Final[list[LiteralString]] = ESSENTIAL + [
    "title",
    "total_time",
    "yields",
]
METHODS: Final[list[LiteralString]] = ON_DISPLAY + [
    "host",
    "image",
    "nutrients"
]
RECIPE_ATTRIBUTES: Final[list[LiteralString]] = METHODS + [
    "url",
    "status",
    "scraper_version"
]


def int2status(t: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(t) != len(RECIPE_ATTRIBUTES):
        raise ValueError(f"Wanted length of {len(RECIPE_ATTRIBUTES)}, got {len(t)}")
    assert RECIPE_ATTRIBUTES[-2] == "status"
    try:
        status = RecipeStatus(int(t[-2]))
    except ValueError:
        status = RecipeStatus.NOT_INITIALIZED
    return t[:-2] + (status, t[-1])


def _get_info(method: str, data: Parsed) -> str:
    log = logger.error if method in ON_DISPLAY else logger.warning

    method_name = method.replace("_", " ")
    try:
        info = getattr(data, method)()
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError, KeyError):
        log("No %s found", method_name)
        return NA
    except NotImplementedError:
        log("%s not implemented for this website", method_name.capitalize())
        return NA
    except Exception as e:
        log("Extraction error: %s", method_name)
        if logger.isEnabledFor(logging.DEBUG):
            exception_trace = "\t" + "\t".join(traceback.format_exception(e))
            logger.debug(exception_trace)
        return NA

    if isinstance(info, (int, float)):
        info = None if info == 0 else str(info)

    if info:
        if method == "ingredients":
            if isinstance(info, list):
                if len(info[0]) < 2:
                    for i in range(len(info)):
                        if not info[i]:
                            info[i] = ' '
                        elif info[i] == ',':
                            info[i] = linesep
                    info = "".join(info)
                else:
                    info = linesep.join(info)
        elif method == "nutrients":
            info = dict2str(info)
        elif method == "instructions":
            if isinstance(info, str):
                info = info.replace(linesep*2, linesep)
            elif isinstance(info, list):
                info = linesep.join(info)
    if not info or info.isspace() or info == "None":
        log("%s contains nothing", method_name.capitalize())
        return NA
    return str(info)


BETWEEN_RECIPES: Final[str] = linesep * 5
HEAD_SEP: Final[str] = linesep * 2


def gen_status(infos: list[str]) -> RecipeStatus:
    if len(infos) > len(METHODS):
        raise ValueError("This function only analyzes attributes contained in html2recipe.methods." +
                         f" Expected {len(METHODS)} elements, got {len(infos)}")
    for i in range(len(ESSENTIAL)):
        if infos[i] == NA:
            return RecipeStatus.INCOMPLETE_ESSENTIAL
    for i in range(len(ESSENTIAL), len(ON_DISPLAY)):
        if infos[i] == NA:
            return RecipeStatus.INCOMPLETE_ON_DISPLAY
    for i in range(len(ON_DISPLAY), len(METHODS)):
        if infos[i] == NA:
            return RecipeStatus.COMPLETE_ON_DISPLAY
    return RecipeStatus.COMPLETE


def parsed2recipe(url: URL, parsed: Parsed) -> Recipe:
    with QCM(logger, logger.info, "Parsing %s", url):
        infos = []
        for method in METHODS:
            infos.append(_get_info(method, parsed))
    status = gen_status(infos)
    recipe = Recipe(url=url, status=status, scraper_version=SCRAPER_VERSION,
                    ingredients=infos[0], instructions=infos[1],
                    title=infos[2], total_time=infos[3], yields=infos[4],
                    host=infos[5], image=infos[6], nutrients=infos[7])
    return recipe


def _re2md(recipe: Recipe) -> list[str]:
    title = recipe.title if recipe.title != NA else recipe.url
    title = esc(title)
    url = esc(recipe.url)
    host = italic(esc(recipe.host))
    if host == NA:
        host = None  # type: ignore

    escaped = [esc(item) for item in recipe.ingredients.split(linesep)]
    ingredients = unordered(*escaped)

    escaped = [esc(step) for step in recipe.instructions.split(linesep)]
    instructions = ordered(*escaped)

    md = [header(title, 2, True), paragraph(),
          recipe.total_time + " min | " + recipe.yields, paragraph()] + \
        ingredients + [EMPTY_COMMENT] + instructions + \
        [paragraph(), italic("from:"), " ", link(url, host), paragraph()]

    return md


def _re2txt(recipe: Recipe) -> list[str]:
    title = recipe.title if recipe.title != NA else recipe.url
    txt = [title,
           HEAD_SEP,
           recipe.total_time + " min | " + recipe.yields + linesep,
           recipe.ingredients,
           linesep * 2,
           recipe.instructions.replace(linesep, linesep * 2),
           linesep,
           "from: " + recipe.url,
           BETWEEN_RECIPES]
    return txt


def recipe2out(recipe: Recipe, counts: Optional[Counts] = None, md: bool = False) -> Optional[list[str]]:
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
        logger.error("Unknown Website. Extraction not supported for %s", url)
        return None
    except AttributeError:
        logger.error("Error while parsing %s", url)
        return None

    return parsed
