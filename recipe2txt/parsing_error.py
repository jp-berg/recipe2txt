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
Module for logging and recording errors occurring during the usage of the :py:mod:`recipe_scrapers`.
"""
import os
import textwrap
import traceback
import urllib
from importlib.metadata import version
from os import linesep
from typing import Callable, Final, NamedTuple

from recipe2txt.file_setup import HOW_TO_REPORT_NAME, get_parsing_error_dir
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.markdown import bold, code, codeblock, italic, unordered
from recipe2txt.utils.misc import URL
from recipe2txt.utils.traceback_utils import format_stacks, get_shared_frames

logger = get_logger(__name__)
"""The logger for the module. Receives the constructed logger from 
:py:mod:`recipe2txt.utils.ContextLogger`"""

SCRAPER_VERSION: Final = version("recipe_scrapers")
"""Contains the version of :py:mod:`recipe_scrapers` currently loaded"""


class ParsingError(NamedTuple):
    """Consists of a TracebackException and the URL of the recipe where the parsing
    failed."""

    url: URL
    traceback: traceback.TracebackException


def handle_parsing_error(
    url: URL,
    exception: Exception,
    method: str | None = None,
    log: Callable[..., None] | None = None,
    save_error: bool = True,
) -> ParsingError | None:
    """
    Logs and categorizes exceptions occurring during parsing of recipes.

    Args:
        url: The URL corresponding to the recipe that was not parsed correctly
        exception: The exception that occured during parsing of the recipe
        method: On which of :py:data:`METHODS` did the exception occur ('None' if the
        error did not occur through
        calling a method on a :py:data:`Parsed`-object
        log: a logging method (e.g. logger.info, logger.critical...) to report the
        occurence of an error
        save_error: Whether the error should be stored in :py:data:`categorized_errors`

    Returns:
        The :py:class:`ParsingError` generated from the parameters
    """
    exception_name = type(exception).__name__
    log = log if log else logger.error
    if method:
        log("No %s found: ", method, exc_info=exception)
    else:
        log("Parsing error: ", exc_info=exception)

    if not save_error:
        return None

    parsing_error = ParsingError(
        url=url, traceback=traceback.TracebackException.from_exception(exception)
    )
    method = method if method else "general parsing error"
    host = urllib.parse.urlparse(url).hostname
    if not host:
        logger.warning("Could not extract host from %s ", url)
        host = url
    if host in categorized_errors:
        if method in categorized_errors[host]:
            if exception_name in categorized_errors[host][method]:
                categorized_errors[host][method][exception_name].append(parsing_error)
            else:
                categorized_errors[host][method][exception_name] = [parsing_error]
        else:
            categorized_errors[host][method] = {exception_name: [parsing_error]}
    else:
        categorized_errors[host] = {method: {exception_name: [parsing_error]}}

    return parsing_error


def errors2str() -> list[tuple[str, str]]:
    """
    Generates a textual representation for every :py:class`ParsingError`stored in
    :py:data:`categorized_errors`

    These markdown-formatted representations are intended to be copy&pasted into the
    text-field of a Github-issue, thus
    reducing friction for reporting errors. If there are multiple occurrences of an
    error¹ () all occurences are grouped
    into the same text. One stack-trace is shown fully, all other traces will have
    all shared² frames except one
    removed.

    1: It is considered the same error, if the host of the recipe-url,
    the :py:data:`METHOD` that caused the error and
    the name of the exception are all the same.

    2: Frames that are exactly the same for all stack traces

    Returns:
        A list of tuples. Each tuple contains the title for the issue and the textual
        representation
    """
    reports = []
    for host, methoddict in categorized_errors.items():
        for method, exception_names in methoddict.items():
            for exception_name, parsing_error_list in exception_names.items():
                msg = PRE_CHECK_MSG

                host = host[4:] if host.startswith("www.") else host
                title = (
                    f"{host.split('.')[0]}: {method} - {exception_name} (found by"
                    " recipe2txt)"
                )

                urls = [parsing_error.url for parsing_error in parsing_error_list]
                triggered_by = (
                    "scrape_html()"
                    if method == "general parsing error"
                    else f".{method}()"
                )
                infos = unordered(
                    "host: " + code(host),
                    "recipe-scrapers version: " + code(SCRAPER_VERSION),
                    "exception: " + code(exception_name),
                    "triggered by calling: " + code(triggered_by),
                    "triggered on: ",
                ) + unordered(*urls, level=1)

                tb_ex_list = [error.traceback for error in parsing_error_list]
                shared_frames = get_shared_frames(tb_ex_list)
                formatted_stacks = format_stacks(
                    tb_ex_list, shared_frames, "recipe2txt"
                )

                if len(urls) > 1:
                    dot_explanation = (
                        italic(
                            "'...' indicates frames present in all traces"
                            "(but only shown in the first)"
                        )
                        + linesep * 2
                    )
                else:
                    dot_explanation = ""

                stack_traces = [f"{bold('Stack Traces')}{linesep * 2}", dot_explanation]

                for error, stack in zip(parsing_error_list, formatted_stacks):
                    stack_traces.append(f"URL: {error.url}{linesep * 2}")
                    stack_traces += codeblock(*stack, language="python")
                    stack_traces.append(linesep * 2)

                msg += "".join(infos) + linesep + "".join(stack_traces)
                reports.append((title, msg))

    return reports


categorized_errors: dict[str, dict[str, dict[str, list[ParsingError]]]] = dict()
"""
A dictionary for categorizing :py:class:`ParsingErrors` based on metadata.

The variable contains three levels of dictionary-nesting. The outer dictionary maps 
the hosts of URLs to further dictionaries. 
Those further dictionaries map a method-name (see :py:data:`METHODS`) to more 
dictionaries. Those dictionaries map
the name of the exception from :py:attr:`ParsingError.traceback` to lists containing 
parsing errors.
Overview:
    outer dictionary (host of url -> middle dictionaries)
    middle dictionary (method where the traceback occured -> inner dictionaries)
    inner dictionary(name of the exception that caused the traceback -> list of 
    parsing errors)


The categorized errors will be used to generate markdown-formatted files, that can be 
submitted as Github-Issues.
This nested-dictionary-abomination is used to group similar errors together, so that 
the can all be reported in one
issue.
"""

PRE_CHECK_MSG: Final = textwrap.dedent("""
    --- MESSAGE GENERATED BY recipe2txt ---
    
    **Pre-filing checks**
    
    - [ ] I have searched for open issues that report the same problem
    - [ ] I have checked that the bug affects the latest version of the library
    
    **Information**
    
    """)
"""String that will be prepended to every error report"""


def write_errors(debug: bool = False) -> int:
    """
    Writes the error reports from :py:func:`recipe2txt.html2recipe.errors2str` to a
    timestamped directory.

    Args:
        debug: Whether the reports should be written into the normal- or into the
        debug-state-directory

    Returns:
        Number of errors written

    """
    if not (errors := errors2str()):
        return 0

    logger.info("---Writing error reports---")

    if not (error_dir := get_parsing_error_dir(debug)):
        return 0
    how_to_report_file = error_dir.parent / HOW_TO_REPORT_NAME

    for title, msg in errors:
        filename = (error_dir / title).with_suffix(".md")
        filename.write_text(msg)

    warn_msg = (
        "During its execution the program encountered recipes "
        f"that could not be (completely) scraped.{os.linesep}"
        f"Please see {os.linesep}%s{os.linesep}if you want to help fix this."
    )
    logger.warning(warn_msg, how_to_report_file)

    return len(errors)
