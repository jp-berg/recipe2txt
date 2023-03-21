from typing import NewType, Final, Callable, Tuple, Optional, NamedTuple
import traceback

from recipe2txt.utils.misc import dprint, Context, nocontext, URL, Counts
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[str] = "N/A"


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
        if method == "total_time": info = str(info)
        elif method == "ingredients": info = "\n".join(info)
        elif method == "instructions_list": info = "\n\n".join(info)
    if not info or info.isspace():
        dprint(1, "\t", method_name.capitalize(), "contains nothing", context=context)
        return NA
    return info


methods: Final[list[str]]= [
    "title",
    "total_time",
    "yields",
    "ingredients",
    "instructions_list"
]

between_recipes: Final[str] = "\n\n\n\n\n"
head_sep: Final[str] = "\n\n"


def parsed2recipe(url: URL, parsed: Parsed,
                  context: Context,
                  counts: Optional[Counts] = None
                  ) -> Optional[str]:
    info = {}
    for method in methods:
        info[method] = _get_info(method, parsed, context=context)
        if info[method] is NA: context = nocontext

    if info["ingredients"] is NA and info["instructions_list"] is NA:
        dprint(1, "\t", "Nothing worthwhile could be extracted. Skipping...", context=context)
        return None
    else:
        recipe = "\n".join([info["title"],
                            head_sep,
                            info["total_time"] + " min    " + info["yields"] + "\n",
                            info["ingredients"],
                            "\n\n",
                            info["instructions_list"],
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

    return parsed
