from typing import NewType, Final, Optional, NamedTuple
import traceback

from recipe2txt.utils.misc import dprint, Context, nocontext, URL, Counts, dict2str
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[str] = "N/A"


class Recipe(NamedTuple):
    url: URL
    host: str
    title: str
    total_time: str
    image: str
    ingredients: str
    instructions: str
    yields: str
    nutrients: str


def _get_info(method: str, data: Parsed, context: Context) -> str:
    method_name = method.replace("_", " ")
    try:
        info = getattr(data, method)()
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError):
        dprint(1, "\t", "No", method_name, "found", context=context)
        return NA
    except NotImplementedError:
        dprint(1, "\t", method_name.capitalize(), "not implemented for this website", context=context)
        return NA
    except Exception as e:
        dprint(1, "\t", "Extraction error", method_name, context=context)
        exception_trace = "\t" + "\t".join(traceback.format_exception(e))
        dprint(4, exception_trace)
        return NA

    if info:
        if method == "total_time":
            if info == 0:
                info = NA
            else:
                info = str(info)
        elif method == "ingredients": info = "\n".join(info)
        elif method == "nutrients": info = dict2str(info)
    if not info or info.isspace() or info == "None":
        dprint(1, "\t", method_name.capitalize(), "contains nothing", context=context)
        return NA
    return info


methods: Final[list[str]] = [
    "host",
    "title",
    "total_time",
    "image",
    "ingredients",
    "instructions",
    "yields",
    "nutrients"
]

between_recipes: Final[str] = "\n\n\n\n\n"
head_sep: Final[str] = "\n\n"


def parsed2recipe(url: URL, parsed: Parsed, context: Context) -> Recipe:
    infos = []
    for method in methods:
        infos.append(_get_info(method, parsed, context))
        if infos[-1] is NA: context = nocontext
    recipe = Recipe(url=url, host=infos[0], title=infos[1], total_time=infos[2],
                    image=infos[3], ingredients=infos[4], instructions=infos[5],
                    yields=infos[6], nutrients=infos[7])
    return recipe


def recipe2txt(recipe: Recipe, counts: Optional[Counts] = None) -> Optional[str]:
    if recipe.ingredients is NA and recipe.instructions is NA:
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


def html2parsed(url: URL, content: str, context: Context) -> Optional[Parsed]:
    try:
        parsed: Parsed = Parsed(recipe_scrapers.scrape_html(html=content, org_url=url))
    except (WebsiteNotImplementedError,
            NoSchemaFoundInWildMode):
        dprint(1, "\t", "Unknown Website. Extraction not supported. Skipping...", context=context)
        return None
    except AttributeError:
        dprint(1, "\t", "Error while parsing website. Skipping...", context=context)
        return None

    return parsed
