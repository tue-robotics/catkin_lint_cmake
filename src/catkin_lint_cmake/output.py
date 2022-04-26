import io
from abc import ABC, abstractmethod

from catkin_lint.linter import Message, ERROR, WARNING, NOTICE
from catkin_lint.output import Color, isatty
import xml.etree.ElementTree as ET


# class Tee:
#     def __init__(self, *args, **kwargs):
#         self._streams = args
#         self.errors = None
#
#     def write(self, data):
#         data = str(data)
#         for s in self._streams:
#             s.write(data)
#
#     def writelines(self, lines):
#         for line in lines:
#             self.write(line)
#
#     def flush(self):
#         for s in self._streams:
#             s.flush()
#
#     def isatty(self):
#         return False


class Output(ABC):
    def __init__(self, pkg, time, stdout, stderr):
        self._pkg = pkg
        self._time = time
        self._stdout = stdout
        self._stderr = stderr

        self._errors = 0
        self._failures = 0
        self._skipped = 0

    @abstractmethod
    def _add_error(self, msg: Message):
        pass

    @abstractmethod
    def _add_failure(self, msg: Message):
        pass

    @abstractmethod
    def _add_skipped(self, msg: Message):
        pass

    def add_error(self, msg: Message):
        self._add_error(msg)
        self._errors += 1

    def add_failure(self, msg: Message):
        self._add_failure(msg)
        self._failures += 1

    def add_skipped(self, msg: Message):
        self._add_skipped(msg)
        self._skipped += 1

    @property
    def number_errors(self):
        return self._errors

    @property
    def number_failures(self):
        return self._failures

    @property
    def number_skipped(self):
        return self._skipped

    @property
    def total_issues(self):
        return self.number_errors + self.number_failures

    @property
    def number_successes(self):
        return int(not self.total_issues)


class TextOutput(Output):

    diagnostic_label = {ERROR: "error", WARNING: "warning", NOTICE: "notice"}

    def __init__(self, pkg, time, stdout, stderr, stream, color=Color.Auto):
        super().__init__(pkg, time, stdout, stderr)
        self._stream = stream

        self._color = color
        self._err_buf = io.StringIO()
        self._fail_buf = io.StringIO()
        self._skip_buf = io.StringIO()

    def _add_msg(self, msg, buffer):
        use_color = self._color == Color.Always or (self._color == Color.Auto and isatty(self._stream))
        if msg.file:
            if msg.line:
                fn = f"{msg.file}({msg.line})"
            else:
                fn = msg.file
            location = f"{msg.package}: {fn}"
        else:
            location = msg.package
        if msg.level:
            header = f" {Color.switch_on[use_color][msg.level]}{self.diagnostic_label[msg.level]}{Color.switch_off[use_color]}:"
        else:
            header = ""
        print(
            f"{location}: {header}{msg.text}\n",
            file=buffer,
        )

    def _add_error(self, msg: Message):
        self._add_msg(msg, self._err_buf)

    def _add_failure(self, msg: Message):
        self._add_msg(msg, self._fail_buf)

    def _add_skipped(self, msg: Message):
        self._add_msg(msg, self._skip_buf)

    def write(self):
        self._stream.write(self._err_buf.getvalue())
        self._stream.write(self._fail_buf.getvalue())
        self._stream.write(self._skip_buf.getvalue())
        header = f"Checked '{self._pkg}' in {self._time} seconds."
        if self.number_successes:
            if self.number_skipped:
                self._stream.write(f"{header} Found {self.number_skipped} skipped test(s)")
            else:
                self._stream.write(f"{header} Found no issues")
        else:
            self._stream.write(
                f"{header} Found {self.number_errors} error(s), {self.number_failures} failure(s), {self.number_skipped} skipped test(s)"
            )


class XmlOutput(Output):
    def __init__(self, pkg, time, stdout, stderr, stream):
        super().__init__(pkg, time, stdout, stderr)
        self._stream = stream

        self._root = ET.Element("testsuite")
        self._root["name"] = "catkin_lint"
        self._root["time"] = round(time, 4)

    def _add_msg(self, msg: Message, issue_type: str = ""):
        testcase = ET.SubElement(self._root, "testcase")
        testcase["time"] = 0.000
        self._add_testcase_name(testcase, msg)
        if issue_type:
            child = ET.SubElement(testcase, issue_type)
            if msg.id:
                child["type"] = msg.id
            if msg.text:
                child["message"] = msg.text

    def _add_error(self, msg):
        self._add_msg(msg, "error")

    def _add_failure(self, msg: Message):
        self._add_msg(msg, "failure")

    def _add_skipped(self, msg: Message):
        self._add_msg(msg, "skipped")

    @staticmethod
    def _add_testcase_name(testcase: ET.Element, msg: Message):
        if msg.file:
            if msg.line:
                testcase["name"] = f"{msg.package}:{msg.file}({msg.line})"
            else:
                testcase["name"] = f"{msg.package}:{msg.file}"
        else:
            testcase["name"] = f"{msg.package}"

    def _add_stats(self):
        self._root["tests"] = self.total_issues + self.number_skipped + self.number_successes
        self._root["errors"] = self.number_errors
        self._root["failures"] = self.number_failures
        self._root["skipped"] = self.number_skipped
        self._root["success"] = self.number_successes

    def write(self):
        if self.total_issues == 0:
            msg = Message(self._pkg, "", 0, "", "", "", "")
            self._add_msg(msg)

        self._add_stats()

        if self._stdout:
            stdout = ET.SubElement(self._root, "system-out")
            stdout.text = f"<![CDATA[{self._stdout}]]>"

        if self._stderr:
            stderr = ET.SubElement(self._root, "system-err")
            stderr.text = f"<![CDATA[{self._stderr}]]>"

        tree = ET.ElementTree(self._root)
        tree.write(self._stream, encoding="utf-8", xml_declaration=True)


class Report:
    def __init__(self, *args):
        self._outputs = args

        self._errors = []
        self._failures = []
        self._skipped = []

    @property
    def errors(self):
        return self._errors

    # @property
    # def number_errors(self):
    #     return len(self._errors)

    @property
    def failures(self):
        return self._failures

    # @property
    # def number_failures(self):
    #     return len(self._failures)

    @property
    def skipped(self):
        return self._skipped

    # @property
    # def number_skipped(self):
    #     return len(self._skipped)
    #
    # @property
    # def total_issues(self):
    #     return self.number_errors + self.number_failures

    def add_failure(self, failure: Message):
        self._failures.append(failure)

    def add_error(self, error: Message):
        self._errors.append(error)

    def add_skipped(self, skip: Message):
        self._skipped.append(skip)

    def write(self):
        for error in self.errors:
            for output in self._outputs:
                output.add_error(error)
        for failure in self.failures:
            for output in self._outputs:
                output.add_failure(failure)
        for skip in self.skipped:
            for output in self._outputs:
                output.add_skipped(skip)

        for output in self._outputs:
            output.write()
