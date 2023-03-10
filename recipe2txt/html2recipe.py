from typing import NewType, Final, Callable, Tuple, Optional, NamedTuple
import traceback

from recipe2txt.utils.misc import dprint, Context, nocontext, URL, Counts
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode, SchemaOrgException, \
    ElementNotFoundInHtml

Parsed = NewType('Parsed', recipe_scrapers._abstract.AbstractScraper)
NA: Final[str] = "N/A"


class Instruction(NamedTuple):
    name: str
    action: Callable[[Parsed], str]


def _get_info(instruction: Instruction, data: Parsed, context: Context) -> str:
    try:
        info = instruction.action(data)
        if not info or info.isspace():
            dprint(1, "\t", instruction.name.capitalize(), "contains nothing", context=context)
            info = NA
        return info
    except (SchemaOrgException, ElementNotFoundInHtml, TypeError, AttributeError):
        dprint(1, "\t", "No", instruction.name, "found", context=context)
    except NotImplementedError:
        dprint(1, "\t", instruction.name.capitalize(), "not implemented for this website", context=context)
    except Exception as e:
        dprint(1, "\t", "Extraction error", name, context=context)
        exception_trace = "\t" + "\n\t".join(traceback.format_exception(e))
        dprint(4, exception_trace)

    return NA


extraction_instructions: Final[list[Instruction]] = [
    Instruction("title", lambda data: str(data.title())),
    Instruction("total time", lambda data: str(data.total_time())),
    Instruction("yields", lambda data: str(data.yields())),
    Instruction("ingredients", lambda data: "\n".join(data.ingredients())),
    Instruction("instructions", lambda data: "\n\n".join(data.instructions_list()))
]
between_recipes: Final[str] = "\n\n\n\n\n"
head_sep: Final[str] = "\n\n"


def parsed2recipe(url: URL, parsed: Parsed,
                  context: Context,
                  counts: Optional[Counts] = None
                  ) -> Optional[str]:
    info = {}
    for instruction in extraction_instructions:
        info[instruction.name] = _get_info(instruction, parsed, context=context)
        if info[instruction.name] is NA: context = nocontext

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

    return parsed
