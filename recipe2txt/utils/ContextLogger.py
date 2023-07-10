import contextlib
import asyncio
import logging
from os import linesep
from logging.handlers import RotatingFileHandler
from types import TracebackType
from typing import Final, Callable, Literal, Any, Generator, Optional
from sys import version_info
if version_info >= (3, 11):
    from typing import LiteralString
else:
    from typing_extensions import LiteralString

string2level: Final[dict[LiteralString, int]] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}

LOGFILE: Final[LiteralString] = "file.log"

_LOG_FORMAT_STREAM: Final[LiteralString] = "%(ctx)s%(message)s"
_LOG_FORMAT_FILE: Final[LiteralString] = "%(asctime)s - %(levelname)s %(module)s:%(funcName)s:%(lineno)d %(message)s"
DATEFMT: Final[LiteralString] = "%Y-%m-%d %H:%m:%S"

CTX_ATTR: Final[LiteralString] = "is_context"
DEFER_EMIT: Final[LiteralString] = "defer_emit"
IS_CONTEXT: Final[dict[str, bool]] = {CTX_ATTR: True}
END_CONTEXT: Final[dict[str, bool]] = {CTX_ATTR: False}
WHILE: Final[str] = f"While %s:{linesep}\t"
DO_NOT_LOG: Final[LiteralString] = "THIS MESSAGE SHOULD NOT BE LOGGED"
DEFAULT_CONTEXT: Final[LiteralString] = "default_context"

logger_list: list[logging.Logger] = []
_stream_handler: Optional[logging.StreamHandler[Any]] = None


class Context:
    def __init__(self) -> None:
        self.context_msg: str = ""
        self.context_args: Any = ()
        self.with_context: bool = False
        self.triggered: bool = False
        self.context_id: int = 0
        self.defer_emit: bool = False
        self.deferred_records: list[logging.LogRecord] = []

    def reset(self) -> None:
        self.context_msg = ""
        self.context_args = ()
        self.with_context = False
        self.triggered = False
        self.context_id = 0
        self.defer_emit = False
        self.deferred_records.clear()

    def dispatch(self, record: logging.LogRecord) -> bool:
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
            return self.dispatch(record)
        else:
            self.with_context = True
            self.context_msg = record.msg
            self.context_args = record.args
            self.triggered = False
            return False

    def close_context(self) -> None:
        if self.with_context and self.deferred_records:
            if _stream_handler:
                for record in self.deferred_records:
                    _stream_handler.emit(record)
            else:
                logging.warning("No stream handler configured.")
        self.reset()

    def get_context(self) -> str:
        if not self.triggered:
            self.context_msg = str(self.context_msg)
            context = WHILE % (self.context_msg[0].lower() + self.context_msg[1:])
            self.triggered = True
            return str(context % self.context_args)
        else:
            return "\t"

    def process(self, record: logging.LogRecord, log_level: int) -> bool:
        record.ctx = ""

        is_context = getattr(record, CTX_ATTR, None)
        if is_context:
            return self.set_context(record, log_level)
        elif is_context is False:
            self.close_context()

        if record.msg == DO_NOT_LOG:
            return False

        if log_level <= record.levelno:  # If record should be emitted
            if self.with_context:
                record.ctx = self.get_context()
            return self.dispatch(record)

        return False


## ASSUMTIONS:  level does not change in context,
##              logger is the only output to the command line
##              No threading while logging


class QueueContextFilter(logging.Filter):
    def __init__(self, log_level: int) -> None:
        self.log_level = log_level
        # TODO: Add reset
        self.tasklocal_context: dict[str, Context] = {DEFAULT_CONTEXT: Context()}

    def get_context(self) -> Context:
        try:
            t = asyncio.current_task()
        except RuntimeError:
            t = None
        task_name = t.get_name() if t else DEFAULT_CONTEXT
        context = self.tasklocal_context.get(task_name)
        if not context:
            context = Context()
            self.tasklocal_context[task_name] = context
        return context

    def set_level(self, log_level: int) -> int:
        if self.get_context().with_context:
            logging.error("Modifying logging-level during context is not possible")
        else:
            self.log_level = log_level
        return self.log_level

    def filter(self, record: logging.LogRecord) -> bool:
        var = self.get_context()
        return var.process(record, self.log_level)


class QueueContextManager:

    def __init__(self, logger: logging.Logger, logging_fun: Callable[..., None], msg: str, *args: Any,
                 defer_emit: bool = False, **kwargs: Any):
        self.args = args
        self.kwargs = kwargs
        self.logging_fun = logging_fun
        self.msg = msg
        self.logger = logger
        self.defer_emit = defer_emit

    def __enter__(self) -> None:
        extra = {CTX_ATTR: True, DEFER_EMIT: self.defer_emit}
        self.logging_fun(self.msg, *self.args, stacklevel=2, extra=extra, **self.kwargs)

    def __exit__(self, exc_type: type, exc_value: BaseException, traceback: TracebackType) -> Literal[False]:
        if not (exc_type or exc_value or traceback):
            self.logger.debug(DO_NOT_LOG, extra=END_CONTEXT)
        else:
            self.logger.error(f"Leaving context '{self.msg % self.args}' because of exception {exc_type}: {exc_value}",
                              extra=END_CONTEXT)
        return False


def disable_loggers() -> None:
    for logger in logger_list:
        logger.disabled = True


def enable_loggers() -> None:
    for logger in logger_list:
        logger.disabled = False


@contextlib.contextmanager
def suppress_logging() -> Generator[None, None, None]:
    disable_loggers()
    yield
    enable_loggers()


class EndContextFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg == DO_NOT_LOG:
            return False
        return True


def get_file_handler(file: str = LOGFILE, level: int = logging.DEBUG) -> logging.FileHandler:
    file_handler = RotatingFileHandler(file, mode='w', maxBytes=100000, backupCount=4, encoding="utf-8")
    file_handler.setLevel(level)
    f = EndContextFilter()
    file_handler.addFilter(f)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT_FILE, datefmt=DATEFMT))
    file_handler.doRollover()
    return file_handler


def get_stream_handler(level: int = logging.WARNING) -> logging.StreamHandler[Any]:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    f = QueueContextFilter(level)
    stream_handler.addFilter(f)
    stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT_STREAM))

    global _stream_handler
    _stream_handler = stream_handler

    return stream_handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger_list.append(logger)
    return logger


def root_log_setup(level: int, file: str | None = None, no_parallel: bool = True) -> None:
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
