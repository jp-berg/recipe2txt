# Copyright (C) 2024 Jan Philipp Berg <git.7ksst@aleeas.com>
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
Module for functions using the jinja2-package to format recipes and write them to files.

"""
from functools import cache

from jinja2 import Environment, StrictUndefined

from recipe2txt.file_setup import JINJA_TEMPLATE_DIR, get_template_files
from recipe2txt.html2recipe import NA, Recipe
from recipe2txt.utils import markdown
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import File, ensure_accessible_file, get_all_dict

logger = get_logger(__name__)


@cache
def get_env() -> Environment:
    """
    Initializes a jinja-Environment

    Adds all functions of the :py:mod:`markdown`-module to the list of available
    filters.

    Returns:
        The jinja-Environment

    """
    env = Environment(undefined=StrictUndefined)
    env.filters |= get_all_dict(markdown)
    return env


def get_template_names() -> set[str]:
    """
    Returns:
        The names of all available jinja-templates
    """
    return set(get_template_files().keys())


class RecipeWriter:
    """
    Associates a file and a .jinja-template that determines the format of the recipes
    written to that file.
    """

    def __init__(self, out: File, template_name: str, debug: bool = False) -> None:
        """

        Args:
            out (): The file to write to
            template_name (): the name of the template (without '.jinja'-extension)
        """
        self.out = out
        if not (template_files := get_template_files(debug)):
            raise FileNotFoundError(
                "No templates found. Empty directory: %s", JINJA_TEMPLATE_DIR
            )
        if not (template_path := template_files.get(template_name)):
            raise ValueError("Template not found: %s", template_name)
        if not (template_file := ensure_accessible_file(template_path)):
            raise FileNotFoundError("Not an accessible File: %s", template_path)
        if not (template_str := template_file.read_text()):
            raise ValueError("Template file is empty: %s", template_file)

        ext = self.out.suffix
        if ext:
            ext = ext[1:] if ext[0] == "." else ext
            if ext != template_name:
                logger.warning(
                    "Out-file-ending (%s) does not match template name (%s)",
                    ext,
                    template_name,
                )
        else:
            self.out.with_suffix("." + template_name)
        if self.out.stat().st_size > 0:
            logger.warning(
                "The output-file already exists and will be overwritten: %s", out
            )

        logger.info("Output set to: %s", self.out)

        self.template = get_env().from_string(template_str)

    def write(self, recipes: list[Recipe]) -> str:
        """
        Formats the recipes and writes them to the file
        Args:
            recipes (): The list of recipes to write
        """
        if recipes:
            logger.info("Writing %s recipes to %s...", len(recipes), self.out)
            recipes_wrapper = {"recipes": recipes, "NA": NA}
            formatted = self.template.render(recipes_wrapper)
            self.out.write_text(formatted)
            return formatted
        else:
            logger.warning("No recipes to write")
            return ""
