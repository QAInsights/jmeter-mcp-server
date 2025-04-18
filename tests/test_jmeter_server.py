import sys
import types
import os
import tempfile
import unittest
from unittest import mock

# Stub external dependencies before importing jmeter_server
sys.modules['mcp'] = types.ModuleType('mcp')
sys.modules['mcp.server'] = types.ModuleType('mcp.server')
fastmcp_mod = types.ModuleType('mcp.server.fastmcp')
class FastMCP:
    def __init__(self, *args, **kwargs):
        pass
    def tool(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def run(self, *args, **kwargs):
        pass
fastmcp_mod.FastMCP = FastMCP
sys.modules['mcp.server.fastmcp'] = fastmcp_mod
# Stub dotenv.load_dotenv
sys.modules['dotenv'] = types.ModuleType('dotenv')
sys.modules['dotenv'].load_dotenv = lambda: None

import jmeter_server


class TestRunJMeter(unittest.IsolatedAsyncioTestCase):
    async def test_file_not_found(self):
        result = await jmeter_server.run_jmeter("nonexistent.jmx")
        self.assertEqual(
            result,
            "Error: Test file not found: nonexistent.jmx"
        )

    async def test_invalid_file_type(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            result = await jmeter_server.run_jmeter(tmp.name)
            self.assertEqual(
                result,
                f"Error: Invalid file type. Expected .jmx file: {tmp.name}"
            )

    @mock.patch('jmeter_server.subprocess.run')
    async def test_non_gui_success(self, mock_run):
        # Prepare a dummy .jmx file
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        # Fake successful subprocess result
        class DummyResult:
            returncode = 0
            stdout = "Success output"
            stderr = ""

        mock_run.return_value = DummyResult()
        result = await jmeter_server.run_jmeter(test_file, non_gui=True)
        self.assertEqual(result, "Success output")
        os.unlink(test_file)

    @mock.patch('jmeter_server.subprocess.run')
    async def test_non_gui_failure(self, mock_run):
        # Prepare a dummy .jmx file
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        # Fake failing subprocess result
        class DummyResult:
            returncode = 1
            stdout = ""
            stderr = "Error occurred"

        mock_run.return_value = DummyResult()
        result = await jmeter_server.run_jmeter(test_file, non_gui=True)
        self.assertEqual(
            result,
            "Error executing JMeter test:\nError occurred"
        )
        os.unlink(test_file)

    @mock.patch('jmeter_server.subprocess.Popen')
    async def test_gui_mode(self, mock_popen):
        # Prepare a dummy .jmx file
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        result = await jmeter_server.run_jmeter(test_file, non_gui=False)
        self.assertEqual(result, "JMeter GUI launched successfully")
        mock_popen.assert_called()
        os.unlink(test_file)

    @mock.patch('jmeter_server.run_jmeter', new_callable=mock.AsyncMock)
    async def test_execute_jmeter_test_default(self, mock_run_jmeter):
        mock_run_jmeter.return_value = "wrapped output"
        result = await jmeter_server.execute_jmeter_test("file.jmx")
        mock_run_jmeter.assert_awaited_with("file.jmx", non_gui=True)
        self.assertEqual(result, "wrapped output")

    @mock.patch('jmeter_server.run_jmeter', new_callable=mock.AsyncMock)
    async def test_execute_jmeter_test_gui(self, mock_run_jmeter):
        mock_run_jmeter.return_value = "gui output"
        result = await jmeter_server.execute_jmeter_test("file.jmx", gui_mode=True)
        mock_run_jmeter.assert_awaited_with("file.jmx", non_gui=False)
        self.assertEqual(result, "gui output")

    @mock.patch('jmeter_server.run_jmeter', new_callable=mock.AsyncMock)
    async def test_execute_jmeter_test_non_gui(self, mock_run_jmeter):
        mock_run_jmeter.return_value = "non-gui output"
        result = await jmeter_server.execute_jmeter_test_non_gui("file.jmx")
        mock_run_jmeter.assert_awaited_with("file.jmx", non_gui=True)
        self.assertEqual(result, "non-gui output")


class TestUnexpectedError(unittest.IsolatedAsyncioTestCase):
    @mock.patch('jmeter_server.Path.resolve', side_effect=Exception("resolve error"))
    async def test_unexpected_error(self, mock_resolve):
        result = await jmeter_server.run_jmeter("any.jmx")
        self.assertTrue(result.startswith("Unexpected error: resolve error"))