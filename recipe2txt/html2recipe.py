# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt. If not, see <https://www.gnu.org/licenses/>.
"""
Module for functions and attributes relating to the recipes themselves.

Attributes:
    logger (logging.Logger): The logger for the module. Receives the constructed
    logger from
            :py:mod:`recipe2txt.utils.ContextLogger`
    Parsed (NewType): Data :py:mod:`recipe_scrapers` extracted from the HTML-file
    NA (LiteralString): Sentinel indicating that the data for this attribute is not
        available
    SCRAPER_VERSION (str): Contains the version of :py:mod:`recipe_scrapers`
    currently loaded
    UNINIT_RECIPE (Recipe): A :py:class:`Recipe` containing only default values for
        attributes
    Recipe-Attribute-Lists: These lists contain the names of :py:class:`Recipe` as
    string. Every attribute-list contains
    all strings of the attribute-list defined before.
        ESSENTIAL (list[LiteralString]): attributes that are considered essential for
        the recipe
        ON_DISPLAY (list[LiteralString]): attributes that are used for creating the
        textual representation of the recipe
        METHODS (list[LiteralString]): attributes that contain information gathered
        by calling the methods with the same
            name on the :py:class:`recipe_scrapers._abstract.AbstractScraper`
        RECIPE_ATTRIBUTES (list[LiteralString]): all attributes in a :py:class:`Recipes`

"""
import re
from enum import IntEnum
from os import linesep
from typing import Any, Final, NamedTuple, NewType

import recipe_scrapers
from importlib_metadata import version
from recipe_scrapers._exceptions import (
    ElementNotFoundInHtml,
    NoSchemaFoundInWildMode,
    SchemaOrgException,
    WebsiteNotImplementedError,
)

from recipe2txt.parsing_error import handle_parsing_error
from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.markdown import (
    EMPTY_COMMENT,
    esc,
    header,
    italic,
    link,
    ordered,
    paragraph,
    unordered,
)
from recipe2txt.utils.misc import NEVER_CATCH, URL, Counts, dict2str, is_url

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from 
:py:mod:`recipe2txt.utils.ContextLogger`"""

Parsed = NewType("Parsed", recipe_scrapers._abstract.AbstractScraper)
"""Data :py:mod:`recipe_scrapers` extracted from the HTML-file"""
NA: Final = "N/A"
"""Sentinel indicating that the data for this attribute is not available"""
SCRAPER_VERSION: Final = version("recipe_scrapers")
"""Contains the version of :py:mod:`recipe_scrapers` currently loaded"""


class RecipeStatus(IntEnum):
    """
    How complete are the information in this :py:class:`Recipe`?

    This status-code always corresponds to one :py:class:`Recipe` and need to be
    continuously updated with every change
    of one or more attributes. Possible states are:
        NOT_INITIALIZED (-1) -> The :py:class:`Recipe` has not been initialized
        UNREACHABLE (0) -> The website corresponding to the URL of the recipe was not
            reachable at the time of creation.
        UNKNOWN (1) -> py:mod:`recipe_scrapers` does not recognize the website of
            this recipe
        INCOMPLETE_ESSENTIAL (2) -> does not contain all attributes named in
            :py:data:`ESSENTIAL`
        INCOMPLETE_ON_DISPLAY (3) -> does not contain all attributes named in
            :py:data:`ON_DISPLAY` but contains
            all attributes listed in :py:data:`ESSENTIAL`
        COMPLETE_ON_DISPLAY (4) -> does not contain all attributes in
            :py:data:`METHODS` but contains all attributes in
            :py:data:`ON_DISPLAY`
        COMPLETE (5) -> does contain all attributes listed in :py:data:`METHODS`
    """

    NOT_INITIALIZED = -1
    UNREACHABLE = 0
    UNKNOWN = 1
    INCOMPLETE_ESSENTIAL = 2
    INCOMPLETE_ON_DISPLAY = 3
    COMPLETE_ON_DISPLAY = 4
    COMPLETE = 5


DUMMY_URL: Final = URL("https://notinitialized.no")
"""An URL representing a faulty or uninitialized value"""


class Recipe(NamedTuple):
    """
    Representation of a recipe.
    """

    ingredients: str = NA
    instructions: str = NA
    title: str = NA
    total_time: str = NA
    yields: str = NA
    host: str = NA
    image: str = NA
    nutrients: str = NA
    url: URL = DUMMY_URL
    status: RecipeStatus = RecipeStatus.NOT_INITIALIZED
    scraper_version: str = "-1"


UNINIT_RECIPE: Final = Recipe()
"""A :py:class:`Recipe` containing only default values for attributes"""


def none2na(t: tuple[Any, ...]) -> tuple[Any, ...]:
    """
    Replaces all 'None'-values in a tuple with :py:data:`NA`-values.

    This function is intended to operate on tuples that will be converted to
    :py:class:`Recipe`.

    Args:
        t: tuple that has no more members than :py:class:`Recipe` has attributes (or
        more than
        :py:data:`RECIPE_ATTRIBUTES`).

    Returns:
        tuple of the same length, but where alle 'None'-values have been replaced
        with :py:data:`NA`-values

    Raises:
        ValueError: If t has more members than the number of attributes of
        :py:class:`Recipe`

    """
    if len(t) > len(RECIPE_ATTRIBUTES):
        raise ValueError(
            f"Expected a Recipe-based tuple (length {len(t)},"
            f" but got something longer (length {len(RECIPE_ATTRIBUTES)})"
        )
    if None in t:
        tmp = list(t)
        t = tuple([
            tmp[i] if tmp[i] else getattr(UNINIT_RECIPE, RECIPE_ATTRIBUTES[i])
            for i in range(len(tmp))
        ])
    return t


ESSENTIAL: Final[list[LiteralString]] = ["ingredients", "instructions"]
"""names of attributes that are considered essential for the recipe"""

ON_DISPLAY: Final[list[LiteralString]] = ESSENTIAL + [
    "title",
    "total_time",
    "yields",
]
"""names of attributes that are used for creating the textual representation of the 
recipe"""

METHODS: Final[list[LiteralString]] = ON_DISPLAY + ["host", "image", "nutrients"]
"""names of attributes that contain information gathered by calling the methods with 
the same name on the 
:py:class:`recipe_scrapers._abstract.AbstractScraper`"""

RECIPE_ATTRIBUTES: Final[list[LiteralString]] = METHODS + [
    "url",
    "status",
    "scraper_version",
]
"""names of all attributes in a :py:class:`Recipes`"""


def int2status(t: tuple[Any, ...]) -> tuple[Any, ...]:
    """
    Convert the int-value of the member on the status position to an
    :py:class:`RecipeStatus`-value.

    This function is intended to operate on tuples that will be converted to
    :py:class:`Recipe`.

    Args:
        t: a tuple with the same number of members as :py:class:`Recipe` has
        attributes. The 10th member should be an
        integer that corresponds to one of the values from :py:class:`RecipeStatus`

    Returns:
        The same tuple but with the 10th member changed from integer to an instance
        of :py:class:`RecipeStatus`

    Raises:
        ValueError: If the length of t does not match the length of
        :py:data:`RECIPE_ATTRIBUTES`
        AssertionError: If :py:mod:`RECIPE_ATTRIBUTES` second last element is not
        equal to "status"
    """
    if len(t) != len(RECIPE_ATTRIBUTES):
        raise ValueError(f"Wanted length of {len(RECIPE_ATTRIBUTES)}, got {len(t)}")
    if RECIPE_ATTRIBUTES[-2] != "status":
        raise AttributeError(
            f"'status' is not at position {len(RECIPE_ATTRIBUTES) -1 -2}"
            " in RECIPE_ATTRIBUTES"
        )
    try:
        status = RecipeStatus(int(t[-2]))
    except ValueError:
        status = RecipeStatus.NOT_INITIALIZED
    return t[:-2] + (status, t[-1])


def get_url(parsed: Parsed) -> URL:
    """
    Extracts the URL from parsed

    Args:
        parsed: The data that the URL should be extracted from

    Returns:
        Either the URL extracted from parsed or in case of failure :py:data:`DUMMY_URL`
    """
    if parsed.url:
        if is_url(parsed.url):
            return parsed.url
        logger.error("Not an URL: %s", parsed.url)
    else:
        logger.error("No URL for parsed data")
    return DUMMY_URL


_contains_alphanumeric = re.compile(r"\w")


def info2str(method: str, info: Any) -> str:
    """
    Processes the data returned by :py:func:`get_info`.

    The function will try to get the info extracted by the method into an (for this
    method) uniform format. Data
    considered invalid for that method (eg. "total_time" -> 0.0) will be replaced
    with :py:data:`NA`.

    Args:
        method: The method that was used to extract info. Has to be one of the
        elements in
        :py:data:`RECIPE_ATTRIBUTES`
        info: The data extracted by the method

    Returns:
        A string representation of info. This representation is uniform for every
        method (e.g. every 'ingredients' is
        a string containing the ingredients separated by line terminators).
    """
    log = logger.error if method in ON_DISPLAY else logger.warning
    unexpected_type = True
    method_name = method.replace("_", " ")

    if info is NA:
        return NA
    if isinstance(info, (int, float)):
        info = None if info == 0 else str(info)
        unexpected_type = False
    elif info:
        if isinstance(info, str):
            unexpected_type = False
        if method == "ingredients":
            if isinstance(info, list):
                if (
                    len(info[0]) < 2
                ):  # Every item in the list is probably just one character
                    for i, c in enumerate(info):
                        if not c:
                            info[i] = " "
                        elif c == ",":
                            info[i] = linesep
                    info = "".join(info)
                else:
                    info = linesep.join(info)
                unexpected_type = False
        elif method == "nutrients":
            if isinstance(info, dict):
                info = dict2str(info)
                unexpected_type = False
        elif method == "instructions":
            if isinstance(info, str):
                info = info.replace(linesep * 2, linesep)
                info = info.replace("\n,", "\n")
                unexpected_type = False
            elif isinstance(info, list):
                info = linesep.join(info)
                unexpected_type = False
    info = info if info and _contains_alphanumeric.search(info) else None
    if not info or info.isspace() or info == "None":
        log("%s contains nothing", method_name.capitalize())
        return NA
    if unexpected_type:
        log("'%s' has the unhandled type %s", method, type(info))
    return str(info)


def get_info(method: str, parsed: Parsed) -> Any:
    """
    Tries to retrieve the raw information from parsed.

    Args:
        method: The :py:data:`METHOD` that should be used for extraction
        parsed ():

    Returns:
        The extracted information or :py:data`NA` should the extraction fail.
    """
    log = logger.error if method in ON_DISPLAY else logger.warning
    method_name = method.replace("_", " ")

    info = NA
    try:
        info = getattr(parsed, method)()
    except (
        SchemaOrgException,
        ElementNotFoundInHtml,
        TypeError,
        AttributeError,
        KeyError,
    ) as e:
        handle_parsing_error(get_url(parsed), e, method_name, log)
    except NotImplementedError:
        log("%s not implemented for this website", method_name.capitalize())
    except NEVER_CATCH:
        raise
    except Exception as e:
        log("Extraction error for attribute %s:", method_name, exc_info=e)

    return info


def gen_status(infos: list[str]) -> RecipeStatus:
    """
    Generates a status value for a list of extracted values.

    Each value in the list should correspond to a string extracted by
    :py:func:`get_info`.

    Args:
        infos ():

    Raises:
        ValueError: If the length of the list does not equal :py:data:`METHODS`

    Returns:
        A recipe-status that matches the values in infos
    """
    if len(infos) > len(METHODS):
        raise ValueError(
            "This function only analyzes attributes contained in html2recipe.methods."
            + f" Expected {len(METHODS)} elements, got {len(infos)}"
        )
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


def parsed2recipe(parsed: Parsed) -> Recipe:
    """
    Converts parsed data to a recipe

    Args:
        parsed: parsed data created by :py:mod:`recipe_scrapers`

    Returns:
        A fully initialized recipe
    """
    logger.info("Parsing HTML")
    infos = []
    for method in METHODS:
        info = get_info(method, parsed)
        info_str = info2str(method, info)
        infos.append(info_str)

    status = gen_status(infos)
    recipe = Recipe(
        url=get_url(parsed),
        status=status,
        scraper_version=SCRAPER_VERSION,
        ingredients=infos[0],
        instructions=infos[1],
        title=infos[2],
        total_time=infos[3],
        yields=infos[4],
        host=infos[5],
        image=infos[6],
        nutrients=infos[7],
    )
    return recipe


def _re2md(recipe: Recipe) -> list[str]:
    title = recipe.title if recipe.title != NA else recipe.url
    title = esc(title)
    url = esc(recipe.url)
    host = None if recipe.host == NA else italic(esc(recipe.host))

    escaped = [esc(item) for item in recipe.ingredients.split(linesep)]
    ingredients = unordered(*escaped)

    escaped = [esc(step) for step in recipe.instructions.split(linesep)]
    instructions = ordered(*escaped)

    md = (
        [
            header(title, 2, True),
            paragraph(),
            recipe.total_time + " min | " + recipe.yields,
            paragraph(),
        ]
        + ingredients
        + [EMPTY_COMMENT]
        + instructions
        + [paragraph(), italic("from:"), " ", link(url, host), paragraph()]
    )

    return md


def _re2txt(recipe: Recipe) -> list[str]:
    title = recipe.title if recipe.title != NA else recipe.url
    txt = [
        title,
        linesep * 2,
        recipe.total_time + " min | " + recipe.yields + linesep * 2,
        recipe.ingredients,
        linesep * 2,
        recipe.instructions.replace(linesep, linesep * 2),
        linesep * 2,
        "from: " + recipe.url,
        linesep * 5,
    ]
    return txt


def recipe2out(
    recipe: Recipe, counts: Counts | None = None, md: bool = False
) -> list[str] | None:
    """
    Formats a recipe for to be written to a file

    Args:
        recipe: The recipe to be formatted
        counts: An optional Counts-object (if statistics should be collected)
        md: Whether the recipe should be formatted for txt or for markdown

    Returns:
        A list of line-terminated strings, where each string represents one line in
        the formatted recipe if the
        recipe contains at least everything mentioned in :data:py:`ESSENTIAL'
        (:py:class:`RecipeStatus` > :py:attr:`RecipeStatus.INCOMPLETE_ESSENTIAL`)
        else None
    """
    if recipe.status <= RecipeStatus.INCOMPLETE_ESSENTIAL:
        logger.error("Nothing worthwhile could be extracted. Skipping...")
        return None
    if counts:
        if recipe.status == RecipeStatus.INCOMPLETE_ON_DISPLAY:
            counts.parsed_partially += 1
        else:
            counts.parsed_successfully += 1

    if md:
        return _re2md(recipe)
    return _re2txt(recipe)


def html2parsed(url: URL, html: str) -> Parsed | None:
    """
    Parses the HTML of the recipe-website.

    Uses :py:mod:`recipe_scrapers to handle the parsing.

    Args:
        url: The URL the HTML was extracted from
        html: The HTML of the recipe-website

    Returns:
        The parsed data if the recipe could be extracted or 'None' if there was a
        failure
    """
    try:
        parsed: Parsed = Parsed(recipe_scrapers.scrape_html(html=html, org_url=url))
    except (WebsiteNotImplementedError, NoSchemaFoundInWildMode):
        logger.error("Unknown Website. Extraction not supported")
        return None
    except (AttributeError, TypeError) as e:
        handle_parsing_error(url, e)
        return None
    except NEVER_CATCH:
        raise
    except Exception as e:
        logger.error("Parsing error: ", exc_info=e)
        return None

    return parsed
