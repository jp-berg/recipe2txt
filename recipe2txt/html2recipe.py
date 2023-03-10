from typing import NewType, Final, Callable, Tuple, Optional
import traceback

from .utils.misc import dprint, Context, nocontext, while_context, URL, Counts
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[str] = "N/A"


def _get_info(name: str, func: Callable[[Parsed], str], data: Parsed, context: Context) -> str:
    try:
        info = func(data)
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
        dprint(4, traceback.print_exception(e))

    return NA


extraction_instructions: Final[list[Tuple[str, Callable[[Parsed], str]]]] = [
    ("title", lambda data: str(data.title())),
    ("total time", lambda data: str(data.total_time())),
    ("yields", lambda data: str(data.yields())),
    ("ingredients", lambda data: "\n".join(data.ingredients())),
    ("instructions", lambda data: "\n\n".join(data.instructions_list()))
]
between_recipes: Final[str] = "\n\n\n\n\n"
head_sep: Final[str] = "\n\n"


def parsed2recipe(url: URL, parsed: Parsed,
                  context: Context,
                  counts: Optional[Counts] = None
                  ) -> Optional[str]:
    info = {}
    for instruction in extraction_instructions:
        info[instruction[0]] = _get_info(*instruction, parsed, context=context)
        if info[instruction[0]] is NA: context = nocontext

    if info["ingredients"] is NA and info["instructions"] is NA:
        dprint(1, "\t", "Nothing worthwhile could be extracted. Skipping...", context=context)
        return None
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

        if counts:
            if NA in info.values():
                counts.parsed_partially += 1
            else:
                counts.parsed_successfully += 1

    return recipe


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

    parsed2recipe(url, parsed, context)
