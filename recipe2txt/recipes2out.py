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

from jinja2 import Environment, StrictUndefined, Template

from recipe2txt.file_setup import get_template_files
from recipe2txt.html2recipe import NA, Recipe
from recipe2txt.utils import markdown
from recipe2txt.utils.misc import File, get_all_dict


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


@cache
def get_template(template_name: str) -> Template | None:
    """
    Generates a template from a config-file

    The config-file must be in the config-folder 'templates'.

    Args:
        template_name (): the name of the template (without '.jinja'-extension)

    Returns:
        The jinja-Template corresponding to template_name

    """
    if not (template := get_template_files().get(template_name)):
        return None

    env = get_env()
    template_str = template.read_text()
    return env.from_string(template_str)


def formatted_to_file(recipes: list[Recipe], template: Template, outfile: File) -> None:
    """
    Formats and writes recipes

    Args:
        recipes (): the recipes to write to outfile
        template (): the template used to format recipes
        outfile (): the file to write the recipes to
    """
    recipes_wrapper = {"recipes": recipes, "NA": NA}
    formatted = template.render(recipes_wrapper)
    outfile.write_text(formatted)


def get_template_names() -> set[str]:
    """
    Returns:
        The names of all available jinja-templates
    """
    return set(get_template_files().keys())
