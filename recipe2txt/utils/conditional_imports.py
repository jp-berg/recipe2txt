# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.

from sys import version_info

if version_info >= (3, 11):
    from typing import LiteralString as LiteralString
else:
    from typing_extensions import LiteralString as LiteralString

if version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum # type: ignore[import-not-found, no-redef]

if version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib # type: ignore[import-not-found, no-redef]


__all__ = ["LiteralString", "StrEnum", "tomllib"]
