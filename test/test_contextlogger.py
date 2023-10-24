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

import logging
import os
import shutil
import unittest
from test.test_helpers import assertFilesEqual, test_project_tmpdir
from test.testfiles.permanent.gen_log import gen_logs, log_paths
from typing import Any, Final, Optional, TypeVar

import recipe2txt.utils.ContextLogger as CTXL
from recipe2txt.utils.conditional_imports import LiteralString
from recipe2txt.utils.misc import File

level = logging.WARNING
test_msg = "THIS IS A TESTMESSAGE"
context_msg = "CONTEXT_MSG: %s %s %s"
context_args = ("This", "is", "a message")


class TestStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        self.seenRecords: list[logging.LogRecord] = []
        self.formattedRecords = []
        self.does_output: bool = False

    def emit(self, record):
        self.seenRecords.append(record)
        if self.does_output:
            super().emit(record)

    def get_formatted_records(self):
        for record in self.seenRecords[len(self.formattedRecords):]:
            self.formattedRecords.append(self.format(record))
        return self.formattedRecords


def get_exc_info(exception: BaseException | None = None):
    if not exception:
        try:
            raise ValueError("DUMMY ERROR")
        except ValueError as e:
            exception = e
    exc_info = (type(exception), exception, exception.__traceback__)
    return exc_info


T = TypeVar('T')


def record_factory(should_trigger: bool, exc_info=None,
                   context: tuple[str, tuple[Any, ...]] | None = None,
                   ctx: str = None, defer: bool = False, is_context: bool | None = None,
                   full_trace: bool = False, msg=None, *args: Any) -> logging.LogRecord:
    global level
    if should_trigger:
        record_level = level + 10
    else:
        record_level = level - 10
        record_level = 0 if record_level < 0 else record_level

    name = "TESTRECORD_FACTORY"
    pathname = "/path/to/file.py"
    lineno = 42
    if not msg:
        if is_context:
            msg = context_msg
            args = context_args
        elif is_context is False:
            msg = CTXL.DO_NOT_LOG
        else:
            msg = test_msg
    func = "TESTFUNC"
    record = logging.LogRecord(name, record_level, pathname, lineno, msg, args, exc_info=exc_info, func=func)
    if context:
        record.context_msg = context[0]
        record.context_args = context[1]
        setattr(record, CTXL.WITH_CTX_ATTR, True)
    if ctx:
        record.ctx = ctx
    if is_context:
        setattr(record, CTXL.CTX_ATTR, True)
        if defer:
            setattr(record, CTXL.DEFER_EMIT, True)
    elif is_context is False:
        setattr(record, CTXL.CTX_ATTR, False)
    if full_trace:
        setattr(record, CTXL.FULL_TRACE_ATTR, True)
    return record


class LoggerTester(unittest.TestCase):
    record_attr: Final[list[LiteralString]] = ["context_args", "context_msg", "msg", "name", "pathname", "with_context",
                                               "exc_info", "exc_text", "filename", "funcName", "levelname", "levelno",
                                               "lineno", "module"]

    context_attr: Final[list[LiteralString]] = ["context_msg", "context_args", "with_context",
                                                "triggered", "defer_emit", "deferred_records"]

    def __init__(self, method_name="runTest"):
        super().__init__(method_name)
        self.stream_handler = TestStreamHandler()
        self.formatter = logging.Formatter("%(message)s")
        self.logger = logging.Logger("test_logger", logging.DEBUG)
        self.logger.addHandler(self.stream_handler)

    def get_context(self, is_context: bool = False, is_emittable: bool = False,
                    deferred: int | None = None) -> CTXL.Context:
        c = CTXL.Context(self.stream_handler)
        if not is_context:
            if deferred is not None:
                raise ValueError("The context cannot have deferred records if there is no active context.")
            return c

        c.with_context = True

        if is_emittable:
            c.triggered = True
        else:
            c.context_msg = context_msg
            c.context_args = context_args
            c.triggered = False

        if deferred is None:
            return c
        elif deferred < 0:
            raise ValueError("Please provide a positive message count")
        else:
            if is_emittable:
                context_record = record_factory(True, defer=True, is_context=True)
                c.deferred_records.append(context_record)
            c.defer_emit = True
            if deferred > 0:
                first_in_context = record_factory(True, context=(context_msg, context_args))
                c.context_args = ()
                c.context_msg = ""
                c.triggered = True
                c.deferred_records.append(first_in_context)
                for i in range(1, deferred):
                    c.deferred_records.append(record_factory(True))
        return c

    def assertAttributeEqual(self, obj1: T, obj2: T, attribute: str) -> None:
        attr1 = getattr(obj1, attribute, None)
        attr2 = getattr(obj2, attribute, None)
        if not attr1 == attr2:
            self.fail(f"Objects differ on '{attribute}': {attr1} vs {attr2}")
        return attr1 == attr2

    def assertRecordEqual(self, record1: logging.LogRecord, record2: logging.LogRecord) -> None:
        if not isinstance(record1, logging.LogRecord):
            self.fail("record1 is not of the class LogRecord")
        if not isinstance(record2, logging.LogRecord):
            self.fail("record2 is not of the class LogRecord")
        for attribute in self.record_attr:
            self.assertAttributeEqual(record1, record2, attribute)

    def assertRecordListsEqual(self, records1: list[logging.LogRecord], records2: logging.LogRecord) -> None:
        if not len(records1) == len(records2):
            self.fail("Length of LogRecord-lists do not match.")
        for idx, (record1, record2) in enumerate(zip(records1, records2)):
            with self.subTest(i=f"Mismatch on index {idx}"):
                self.assertRecordEqual(record1, record2)

    def assertContextEqual(self, context1: CTXL.Context, context2: CTXL.Context) -> None:
        if not isinstance(context1, CTXL.Context):
            raise ValueError("context1 is not of the class Context")
        if not isinstance(context2, CTXL.Context):
            raise ValueError("context2 is not of the class Context")
        for attribute in self.context_attr:
            if attribute == "deferred_records":
                with self.subTest(msg="Mismatch on deferred_records."):
                    self.assertRecordListsEqual(context1.deferred_records, context2.deferred_records)
                    continue
            self.assertAttributeEqual(context1, context2, attribute)

    def assertContextNotEqual(self, context1: CTXL.Context, context2: CTXL.Context):
        try:
            self.assertContextEqual(context1, context2)
            self.fail("Contexts are equal.")
        except self.failureException:
            pass


class TestContext(LoggerTester):

    def tearDown(self) -> None:
        global level
        level = logging.WARNING
        self.stream_handler.seenRecords.clear()

    def test_dispatch(self):
        context_defer = self.get_context(True, True, 3)
        record = record_factory(True)
        self.assertFalse(context_defer.dispatch(record, level))

        context_emit = self.get_context(True, False)
        self.assertTrue(context_emit.dispatch(record, level))

        record_ex = record_factory(True, exc_info=get_exc_info())
        self.assertTrue(context_emit.dispatch(record_ex, level))
        self.assertFalse(getattr(record_ex, CTXL.FULL_TRACE_ATTR))

        self.assertFalse(context_defer.dispatch(record_ex, logging.DEBUG))
        self.assertTrue(getattr(record_ex, CTXL.FULL_TRACE_ATTR))

    def test_set_context(self):
        context_record_emit = record_factory(True, is_context=True)
        test = self.get_context()
        self.assertTrue(test.set_context(context_record_emit, level))
        validation = self.get_context()
        validation.with_context = True
        validation.triggered = True
        self.assertContextEqual(test, validation)

        context_record_swallow = record_factory(False, is_context=True)
        test.reset()
        self.assertFalse(test.set_context(context_record_swallow, level))
        validation = self.get_context(True, False)
        self.assertContextEqual(test, validation)

    def test_close_context(self):
        context = self.get_context(True, True)
        validation = self.get_context()
        self.assertContextNotEqual(context, validation)
        context.close_context()
        self.assertContextEqual(context, validation)

        no_def = 4
        context = self.get_context(is_context=True, deferred=no_def)
        validation = self.get_context(is_context=True, deferred=no_def)

        context.close_context()
        self.assertRecordListsEqual(self.stream_handler.seenRecords, validation.deferred_records)


class TestContextProcess(LoggerTester):

    def setUp(self):
        self.record_normal = record_factory(True)
        self.record_normal_reject = record_factory(False)
        self.record_context = record_factory(True, is_context=True)
        self.record_context_reject = record_factory(False, is_context=True)

        self.record_close_context = record_factory(False, msg=CTXL.DO_NOT_LOG, is_context=False)

        self.context = self.get_context()
        self.validation = self.get_context()
        self.validation_triggered = self.get_context(True, True)

    def tearDown(self) -> None:
        self.stream_handler.seenRecords.clear()
        self.stream_handler.formattedRecords.clear()

    def test_basecase(self):
        self.assertTrue(self.context.process(self.record_normal, level))
        self.assertFalse(self.context.process(self.record_normal_reject, level))
        self.assertContextEqual(self.context, self.validation)

    def test_triggered(self):
        self.assertTrue(self.context.process(self.record_context, level))
        self.assertContextEqual(self.context, self.validation_triggered)

        self.assertTrue(self.context.process(self.record_normal, level))
        self.assertContextEqual(self.context, self.validation_triggered)

    def test_untriggered(self):
        validation_untriggered = self.get_context(True, False)

        self.assertFalse(self.context.process(self.record_context_reject, level))
        self.assertContextEqual(self.context, validation_untriggered)

        self.assertFalse(self.context.process(self.record_normal_reject, level))
        self.assertContextEqual(self.context, validation_untriggered)

        self.assertTrue(self.context.process(self.record_normal, level))
        self.assertContextEqual(self.context, self.validation_triggered)

        self.assertFalse(self.context.process(self.record_close_context, level))
        self.assertContextEqual(self.context, self.validation)

    def test_untriggered_defer(self):
        validation_untriggered_defer = self.get_context(True, False, 0)
        validation_triggered_defer = self.get_context(True, False, 1)
        record_context_defer = record_factory(False, is_context=True, defer=True)

        self.assertFalse(self.context.process(record_context_defer, level))
        self.assertContextEqual(self.context, validation_untriggered_defer)

        self.assertFalse(self.context.process(self.record_normal, level))
        self.assertFalse(self.context.process(self.record_normal_reject, level))
        self.assertContextEqual(self.context, validation_triggered_defer)

        self.assertFalse(self.context.process(self.record_close_context, level))
        self.assertRecordListsEqual(self.stream_handler.seenRecords, validation_triggered_defer.deferred_records)


class TestQueueContextFormatter(LoggerTester):

    def __init__(self, method_name="runTest"):
        super().__init__(method_name)
        self.ctx_unformatted_formatted = \
            [(("Doing stuff", ()), f"While doing stuff:{os.linesep}\t"),
             (("doing %s and %s and also %s", ("thing1", "thing2", "thing3")),
              f"While doing thing1 and thing2 and also thing3:{os.linesep}\t"),
             # ((context_msg, context_args), f"While {context_msg % context_args}:{os.linesep}\t")
             ]

    def test_format_context(self):
        for test, validation in self.ctx_unformatted_formatted:
            with self.subTest(msg=f"Failure while creating '{repr(validation)}'"):
                self.assertEqual(CTXL.format_context(*test), validation)

    def test_add_context(self):
        record = record_factory(True)
        record = CTXL.add_context(record)
        self.assertEqual(record.ctx, "")

        record = record_factory(True)
        setattr(record, CTXL.WITH_CTX_ATTR, True)
        record = CTXL.add_context(record)
        self.assertEqual(record.ctx, "\t")

        records_strs = [(record_factory(True, context=unformatted), formatted)
                        for unformatted, formatted in self.ctx_unformatted_formatted]
        for record, string in records_strs:
            with self.subTest(msg=f"Failure while creating '{repr(string)}'"):
                record = CTXL.add_context(record)
                self.assertEqual(record.ctx, string)


class TestAll(unittest.TestCase):
    def test_logging(self):
        test_path = test_project_tmpdir / "logfiles"
        if test_path.is_dir():
            shutil.rmtree(test_path)
        test_paths: list[File] = gen_logs(test_path)
        for test, validation in zip(test_paths, log_paths):
            with self.subTest(msg=f"While testing {test.name}"):
                assertFilesEqual(self, test, validation)

