import logging
from os import linesep
from logging.handlers import RotatingFileHandler
from types import TracebackType
from typing import Final, Callable, Literal, Optional, Any

string2level: Final[dict[str, int]] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}

logfile: Final[str] = "file.log"

_log_format_stream: Final[str] = f"%(ctx)s %(message)s"
_log_format_file: Final[str] = f"%(asctime)s - %(levelname)s %(module)s:%(funcName)s:%(lineno)d %(message)s"
datefmt: Final[str] = "%Y-%m-%d %H:%m:%S"

CTX_ATTR: Final[str] = "is_context"
IS_CONTEXT: Final[dict[str, bool]] = {CTX_ATTR: True}
END_CONTEXT: Final[dict[str, bool]] = {CTX_ATTR: False}
WHILE: Final[str] = f"While %s:{linesep}\t "
DO_NOT_LOG: Final[str] = "THIS MESSAGE SHOULD NOT BE LOGGED"


## ASSUMTIONS:  no threading/async while context,
##              level does not change in context,
##              logger is the only output to the command line
##              only one context at a time
##              Expensive __str__() is guarded by .isEnabledFor()


class QueueContextFilter(logging.Filter):
    def __init__(self, log_level: int) -> None:
        self.log_level = log_level
        self.context_msg = ""
        self.context_args = ()
        self.with_context = False
        self.triggered = False

    def set_level(self, log_level: int) -> int:
        if self.with_context:
            logging.error("Modifying logging-level during context is not possible")
        else:
            self.log_level = log_level
        return self.log_level

    def filter(self, record: logging.LogRecord) -> bool:
        is_context = getattr(record, CTX_ATTR, None)
        if is_context is False:
            self.context_msg = ""
            self.context_args = ()
            self.with_context = False
            self.triggered = False

        if record.msg == DO_NOT_LOG:
            return False

        if self.log_level <= record.levelno:  # If record should be emitted
            record.ctx = ""
            if not is_context and self.with_context:
                if self.triggered:
                    record.ctx = "\t"
                else:
                    self.context_msg = str(self.context_msg)
                    context = WHILE % (self.context_msg[0].lower() + self.context_msg[1:])
                    record.msg = (context % self.context_args) + str(record.msg)
                    self.triggered = True
            return True

        if is_context:
            self.with_context = True
            self.context_msg = record.msg
            self.context_args = record.args  # type:ignore
            self.triggered = False
        return False


class QueueContextManager:

    def __init__(self, logger: logging.Logger, logging_fun: Callable[..., None], msg: str, *args: Any, **kwargs: Any):
        self.args = args
        self.kwargs = kwargs
        self.logging_fun = logging_fun
        self.msg = msg
        self.logger = logger

    def __enter__(self) -> None:  # TODO: Make enter defer emit until exit
        self.logging_fun(self.msg, *self.args, extra=IS_CONTEXT, **self.kwargs)

    def __exit__(self, exc_type: type, exc_value: BaseException, traceback: TracebackType) -> Literal[False]:
        if not (exc_type or exc_value or traceback):
            self.logger.debug(DO_NOT_LOG, extra=END_CONTEXT)
        else:
            self.logger.error(f"Leaving context '{self.msg % self.args}' because of exception {exc_type}: {exc_value}",
                              extra=END_CONTEXT)
        return False


class EndContextFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        is_context = getattr(record, CTX_ATTR, None)
        if record.msg == DO_NOT_LOG:
            return False
        return True


def get_file_handler(file: str = logfile, level: int = logging.DEBUG) -> logging.FileHandler:
    file_handler = RotatingFileHandler(file, mode='w', maxBytes=100000, backupCount=4, encoding="utf-8")
    file_handler.setLevel(level)
    f = EndContextFilter()
    file_handler.addFilter(f)
    file_handler.setFormatter(logging.Formatter(_log_format_file, datefmt=datefmt))
    file_handler.doRollover()
    return file_handler


def get_stream_handler(level: int = logging.WARNING) -> logging.StreamHandler[Any]:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    f = QueueContextFilter(level)
    stream_handler.addFilter(f)
    stream_handler.setFormatter(logging.Formatter(_log_format_stream))
    return stream_handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger


def root_log_setup(level: int, file: str, no_parallel: bool = True) -> None:
    f = get_file_handler(file)
    s = get_stream_handler(level)
    l = logging.getLogger()

    l.setLevel(logging.DEBUG)
    l.addHandler(f)
    l.addHandler(s)

    if no_parallel:
        logging.logThreads = False
        logging.logProcesses = False
        logging.logMultiprocessing = False

