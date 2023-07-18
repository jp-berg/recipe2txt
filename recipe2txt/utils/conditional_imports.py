from sys import version_info

if version_info >= (3, 11):
    from typing import LiteralString as LiteralString
else:
    from typing_extensions import LiteralString as LiteralString

if version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum # type: ignore


__all__ = ["LiteralString", "StrEnum"]
