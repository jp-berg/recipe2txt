# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.

import asyncio
import contextlib
import logging
import os
import traceback
from logging.handlers import RotatingFileHandler
from os import linesep
from types import TracebackType
from typing import Any, Callable, Final, Generator, Literal, TypeAlias, get_args

from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.utils.traceback_utils import shorten_paths

LOG_LEVEL_NAMES: Final[TypeAlias] = Literal[
    "debug", "info", "warning", "error", "critical"
]
LOG_LEVEL_VALUES: Final[list[int]] = [
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
]

STRING2LEVEL: Final[dict[LiteralString, int]] = dict(
    zip(get_args(LOG_LEVEL_NAMES), LOG_LEVEL_VALUES)
)

LOGFILE: Final = "file.log"

_LOG_FORMAT_STREAM: Final = "%(ctx)s%(message)s"
_LOG_FORMAT_FILE: Final = str(
    "%(asctime)s - %(levelname)s %(module)s:%(funcName)s:%(lineno)d %(message)s"
)

DATEFMT: Final = "%Y-%m-%d %H:%m:%S"

CTX_ATTR: Final = "is_context"
DEFER_EMIT: Final = "defer_emit"
CTX_MSG_ATTR: Final = "context_msg"
CTX_ARGS_ATTR: Final = "context_args"
WITH_CTX_ATTR: Final = "with_context"
FULL_TRACE_ATTR: Final = "full_trace"

END_CONTEXT: Final[dict[str, bool]] = {CTX_ATTR: False}

WHILE: Final = f"While %s:{linesep}\t"
DO_NOT_LOG: Final = "THIS MESSAGE SHOULD NOT BE LOGGED"
DEFAULT_CONTEXT: Final = "default_context"

logger_list: list[logging.Logger] = []


class Context:
    def __init__(self, handler: logging.Handler) -> None:
        self.context_msg: str = ""
        self.context_args: Any = ()
        self.with_context: bool = False
        self.triggered: bool = False
        self.defer_emit: bool = False
        self.deferred_records: list[logging.LogRecord] = []
        self.handler = handler

    def reset(self) -> None:
        self.context_msg = ""
        self.context_args = ()
        self.with_context = False
        self.triggered = False
        self.defer_emit = False
        self.deferred_records.clear()

    def dispatch(self, record: logging.LogRecord, log_level: int) -> bool:
        if record.exc_info:
            setattr(record, FULL_TRACE_ATTR, log_level <= logging.DEBUG)
        if self.defer_emit:
            self.deferred_records.append(record)
            return False
        else:
            return True

    def set_context(self, record: logging.LogRecord, log_level: int) -> bool:
        self.defer_emit = bool(getattr(record, DEFER_EMIT, False))
        self.with_context = True
        if log_level <= record.levelno:
            self.triggered = True
            return self.dispatch(record, log_level)
        else:
            self.with_context = True
            self.context_msg = record.msg
            self.context_args = record.args
            self.triggered = False
            return False

    def close_context(self) -> None:
        if self.with_context and self.deferred_records:
            for record in self.deferred_records:
                self.handler.emit(record)
        self.reset()

    def process(self, record: logging.LogRecord, log_level: int) -> bool:
        is_context = getattr(record, CTX_ATTR, None)
        if is_context:
            return self.set_context(record, log_level)
        elif is_context is False:
            self.close_context()

        if record.msg == DO_NOT_LOG:
            return False

        if log_level <= record.levelno:  # If record should be emitted
            if self.with_context:
                if not self.triggered:
                    setattr(record, CTX_MSG_ATTR, self.context_msg)
                    self.context_msg = ""
                    setattr(record, CTX_ARGS_ATTR, self.context_args)
                    self.context_args = ()
                    self.triggered = True
                setattr(record, WITH_CTX_ATTR, True)
            return self.dispatch(record, log_level)

        return False


## ASSUMTIONS:  level does not change in context,
##              logger is the only output to the command line
##              No threading while logging


class QueueContextFilter(logging.Filter):
    def __init__(
            self, log_level: int = logging.NOTSET,
            handler: logging.Handler | None = None
    ) -> None:
        self.log_level = log_level
        # TODO: Add reset
        self.handler = handler if handler else logging.NullHandler()
        self.tasklocal_context: dict[str, Context] = {
            DEFAULT_CONTEXT: Context(self.handler)
        }

    def set_handler(self, handler: logging.Handler | None = None) -> None:
        self.handler = handler if handler else logging.NullHandler()
        for context in self.tasklocal_context.values():
            context.handler = self.handler

    def get_context(self) -> Context:
        try:
            t = asyncio.current_task()
        except RuntimeError:
            t = None
        task_name = t.get_name() if t else DEFAULT_CONTEXT
        context = self.tasklocal_context.get(task_name)
        if not context:
            context = Context(self.handler)
            self.tasklocal_context[task_name] = context
        return context

    def set_level(self, log_level: int = logging.NOTSET) -> int:
        if self.get_context().with_context:
            logging.error("Modifying logging-level during context is not possible")
        else:
            self.log_level = log_level
        return self.log_level

    def filter(self, record: logging.LogRecord) -> bool:
        if self.log_level is logging.NOTSET:
            logging.warning("Log-level not set")
        if isinstance(self.handler, logging.NullHandler):
            logging.warning("Handler not set")

        var = self.get_context()
        return var.process(record, self.log_level)


def format_exception(
        exc_info: tuple[type[BaseException], BaseException, TracebackType | None],
        indent_for_context: bool = False,
        full: bool = False,
) -> str:
    ex_class, exception, trace = exc_info
    if full:
        tb_ex = traceback.TracebackException.from_exception(exception)
        tb_ex.stack = shorten_paths(tb_ex.stack, first_visible_dir="Rezepte")
        tb = tb_ex.format()
        indent = "\t\t" if indent_for_context else "\t"
        tb_lines = [
            indent + line + os.linesep
            for frame in tb
            for line in frame.split(os.linesep)
            if line
        ]
        formatted = linesep + "".join(tb_lines)
    else:
        formatted = f"{ex_class.__name__} - {exception}"

    return formatted


def format_context(msg: Any, args: Any) -> str:
    msg = str(msg)
    msg = msg[0].lower() + msg[1:]
    msg = WHILE % msg
    return str(msg % args)


def add_context(record: logging.LogRecord) -> logging.LogRecord:
    with_context = getattr(record, WITH_CTX_ATTR, False)
    if with_context:
        context_msg = getattr(record, CTX_MSG_ATTR, None)
        if context_msg:
            fmt_ctx = format_context(context_msg, getattr(record, CTX_ARGS_ATTR, None))
            record.ctx = fmt_ctx
        else:
            record.ctx = "\t"
    else:
        record.ctx = ""
    return record


class QueueContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record = add_context(record)
        exc_info = None
        exc_text = None
        fmt_ex = ""
        if record.exc_info and record.exc_info[0] and record.exc_info[1]:
            exc_info, record.exc_info = record.exc_info, exc_info
            exc_text, record.exc_text = record.exc_text, exc_text
            fmt_ex = format_exception(
                exc_info,
                indent_for_context=bool(getattr(record, "ctx", "")),
                full=getattr(record, FULL_TRACE_ATTR, False),
            )
        s = super().format(record) + fmt_ex

        record.exc_info = exc_info
        record.exc_text = exc_text

        return s


class QueueContextManager:
    def __init__(
            self,
            logger: logging.Logger,
            logging_fun: Callable[..., None],
            msg: str,
            *args: Any,
            defer_emit: bool = False,
            **kwargs: Any,
    ):
        self.args = args
        self.kwargs = kwargs
        self.logging_fun = logging_fun
        self.msg = msg
        self.logger = logger
        self.defer_emit = defer_emit

    def __enter__(self) -> None:
        extra = {CTX_ATTR: True, DEFER_EMIT: self.defer_emit}
        self.logging_fun(self.msg, *self.args, stacklevel=2, extra=extra, **self.kwargs)

    def __exit__(
            self, exc_type: type, exc_value: BaseException, traceback: TracebackType
    ) -> Literal[False]:
        if not (exc_type or exc_value or traceback):
            self.logger.debug(DO_NOT_LOG, extra=END_CONTEXT)
        else:
            self.logger.error(
                f"Leaving context '{self.msg % self.args}' because of exception"
                f" {exc_type}: {exc_value}",
                extra=END_CONTEXT,
            )
        return False


def disable_loggers() -> None:
    for logger in logger_list:
        setattr(logger, "was_disabled", logger.disabled)
        logger.disabled = True


def reset_disable_loggers() -> None:
    for logger in logger_list:
        logger.disabled = getattr(logger, "was_disabled", False)


@contextlib.contextmanager
def suppress_logging() -> Generator[None, None, None]:
    disable_loggers()
    yield
    reset_disable_loggers()


class EndContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg == DO_NOT_LOG:
            return False
        return True


def get_file_handler(
        file: str = LOGFILE, level: int = logging.DEBUG
) -> logging.FileHandler:
    file_handler = RotatingFileHandler(
        file, mode="w", maxBytes=10000000, backupCount=4, encoding="utf-8"
    )
    file_handler.setLevel(level)
    f = EndContextFilter()
    file_handler.addFilter(f)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT_FILE, datefmt=DATEFMT))
    file_handler.doRollover()
    return file_handler


def get_stream_handler(
        level: int = logging.WARNING) -> logging.StreamHandler:  # type: ignore [
    # type-arg]
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    f = QueueContextFilter(level, stream_handler)
    stream_handler.addFilter(f)
    stream_handler.setFormatter(QueueContextFormatter(_LOG_FORMAT_STREAM))

    return stream_handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger_list.append(logger)
    return logger


def root_log_setup(
        level: int, file: str | None = None, no_parallel: bool = True
) -> None:
    l = logging.getLogger()

    l.setLevel(logging.DEBUG)
    if file:
        f = get_file_handler(file)
        l.addHandler(f)
    s = get_stream_handler(level)
    l.addHandler(s)
    logger_list.append(l)

    if no_parallel:
        logging.logThreads = False
        logging.logProcesses = False
        logging.logMultiprocessing = False
