import sys
import types
import os
import signal
import time
import asyncio
import contextlib
import io
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

    def _make_proc(self, stdout=b"", stderr=b"", returncode=0):
        proc = mock.MagicMock()
        proc.communicate = mock.AsyncMock(return_value=(stdout, stderr))
        proc.wait = mock.AsyncMock()
        proc.returncode = returncode
        return proc

    @mock.patch('jmeter_server.asyncio.create_subprocess_exec', new_callable=mock.AsyncMock)
    async def test_non_gui_success(self, mock_exec):
        # Prepare a dummy .jmx file
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        mock_exec.return_value = self._make_proc(stdout=b"Success output")
        result = await jmeter_server.run_jmeter(test_file, non_gui=True)
        self.assertEqual(result, "Success output")
        os.unlink(test_file)

    @mock.patch('jmeter_server.asyncio.create_subprocess_exec', new_callable=mock.AsyncMock)
    async def test_non_gui_failure(self, mock_exec):
        # Prepare a dummy .jmx file
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        mock_exec.return_value = self._make_proc(stderr=b"Error occurred", returncode=1)
        result = await jmeter_server.run_jmeter(test_file, non_gui=True)
        self.assertEqual(
            result,
            "Error executing JMeter test (exit code 1):\nError occurred"
        )
        os.unlink(test_file)

    @mock.patch('jmeter_server.asyncio.wait_for', new_callable=mock.AsyncMock)
    @mock.patch('jmeter_server.asyncio.create_subprocess_exec', new_callable=mock.AsyncMock)
    async def test_non_gui_timeout(self, mock_exec, mock_wait_for):
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        proc = self._make_proc()
        mock_exec.return_value = proc
        mock_wait_for.side_effect = asyncio.TimeoutError
        with mock.patch.dict(os.environ, {'JMETER_TIMEOUT_SECONDS': '5'}), \
             mock.patch('jmeter_server.os.killpg') as mock_killpg:
            result = await jmeter_server.run_jmeter(test_file, non_gui=True)
        self.assertIn("timed out after 5.0 seconds", result)
        _, kwargs = mock_exec.call_args
        self.assertTrue(kwargs.get('start_new_session'))
        if os.name == 'posix':
            mock_killpg.assert_called_once_with(proc.pid, signal.SIGKILL)
        else:
            proc.kill.assert_called_once()
        proc.wait.assert_awaited_once()
        os.unlink(test_file)

    @mock.patch('jmeter_server.asyncio.create_subprocess_exec', new_callable=mock.AsyncMock)
    async def test_non_gui_log_file_without_report(self, mock_exec):
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        mock_exec.return_value = self._make_proc(stdout=b"done")
        await jmeter_server.run_jmeter(test_file, non_gui=True, log_file="out.jtl")
        cmd = list(mock_exec.call_args.args)
        self.assertIn('-l', cmd)
        self.assertEqual(cmd[cmd.index('-l') + 1], 'out.jtl')
        self.assertNotIn('-e', cmd)
        self.assertNotIn('-o', cmd)
        os.unlink(test_file)

    @mock.patch('jmeter_server.asyncio.create_subprocess_exec', new_callable=mock.AsyncMock)
    async def test_non_gui_generate_report_generates_log_file(self, mock_exec):
        with tempfile.NamedTemporaryFile(suffix=".jmx", delete=False) as tmp:
            test_file = tmp.name
        mock_exec.return_value = self._make_proc(stdout=b"done")
        await jmeter_server.run_jmeter(test_file, non_gui=True, generate_report=True)
        cmd = list(mock_exec.call_args.args)
        self.assertIn('-l', cmd)
        self.assertIn('-e', cmd)
        self.assertIn('-o', cmd)
        self.assertEqual(cmd.count('-l'), 1)
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
        mock_run_jmeter.assert_awaited_with("file.jmx", non_gui=True, properties=None)
        self.assertEqual(result, "wrapped output")

    @mock.patch('jmeter_server.run_jmeter', new_callable=mock.AsyncMock)
    async def test_execute_jmeter_test_gui(self, mock_run_jmeter):
        mock_run_jmeter.return_value = "gui output"
        result = await jmeter_server.execute_jmeter_test("file.jmx", gui_mode=True)
        mock_run_jmeter.assert_awaited_with("file.jmx", non_gui=False, properties=None)
        self.assertEqual(result, "gui output")

    @mock.patch('jmeter_server.run_jmeter', new_callable=mock.AsyncMock)
    async def test_execute_jmeter_test_non_gui(self, mock_run_jmeter):
        mock_run_jmeter.return_value = "non-gui output"
        result = await jmeter_server.execute_jmeter_test_non_gui("file.jmx")
        mock_run_jmeter.assert_awaited_with("file.jmx", non_gui=True, properties=None, generate_report=False, report_output_dir=None, log_file=None)
        self.assertEqual(result, "non-gui output")


@unittest.skipUnless(os.name == 'posix', 'process-group kill requires posix')
class TestTimeoutKillsProcessTree(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_kills_child_process(self):
        with tempfile.TemporaryDirectory() as d:
            test_file = os.path.join(d, "test.jmx")
            open(test_file, 'w').write("<jmeterTestPlan/>")
            pid_file = os.path.join(d, "child.pid")
            fake_jmeter = os.path.join(d, "jmeter")
            with open(fake_jmeter, 'w') as f:
                f.write(f"#!/bin/sh\nsleep 30 & child=$!; echo $child > {pid_file}; wait $child\n")
            os.chmod(fake_jmeter, 0o755)

            with mock.patch.dict(os.environ, {
                'JMETER_BIN': fake_jmeter,
                'JMETER_TIMEOUT_SECONDS': '1',
            }):
                result = await jmeter_server.run_jmeter(test_file, non_gui=True)

            self.assertIn("timed out", result)
            with open(pid_file) as f:
                child_pid = int(f.read().strip())
            # Poll up to 2s for the child to die
            alive = True
            for _ in range(20):
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    alive = False
                    break
                time.sleep(0.1)
            self.assertFalse(alive, f"child process {child_pid} still alive after timeout")


class TestUnexpectedError(unittest.IsolatedAsyncioTestCase):
    @mock.patch('jmeter_server.Path.resolve', side_effect=Exception("resolve error"))
    async def test_unexpected_error(self, mock_resolve):
        result = await jmeter_server.run_jmeter("any.jmx")
        self.assertTrue(result.startswith("Unexpected error: resolve error"))


class TestGetTimeoutSeconds(unittest.TestCase):
    def test_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('JMETER_TIMEOUT_SECONDS', None)
            self.assertEqual(jmeter_server._get_timeout_seconds(), 3600.0)

    def test_zero_means_no_timeout(self):
        with mock.patch.dict(os.environ, {'JMETER_TIMEOUT_SECONDS': '0'}):
            self.assertIsNone(jmeter_server._get_timeout_seconds())

    def test_invalid_uses_default(self):
        with mock.patch.dict(os.environ, {'JMETER_TIMEOUT_SECONDS': 'abc'}):
            self.assertEqual(jmeter_server._get_timeout_seconds(), 3600.0)

    def test_valid_value(self):
        with mock.patch.dict(os.environ, {'JMETER_TIMEOUT_SECONDS': '120'}):
            self.assertEqual(jmeter_server._get_timeout_seconds(), 120.0)


class TestTruncateOutput(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(jmeter_server._truncate_output("line1\nline2", max_lines=200), "line1\nline2")

    def test_long_text_truncated(self):
        text = "\n".join(f"line{i}" for i in range(300))
        result = jmeter_server._truncate_output(text, max_lines=200)
        lines = result.splitlines()
        self.assertEqual(len(lines), 201)
        self.assertIn("100 earlier lines omitted", lines[0])
        self.assertEqual(lines[-1], "line299")

    def test_empty_string(self):
        self.assertEqual(jmeter_server._truncate_output(""), "")


JTL_HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"


def _write_jtl(dirpath):
    """Write a small CSV JTL fixture: ~20 rows over >10 seconds, 2 labels."""
    path = os.path.join(dirpath, "results.jtl")
    base_ts = 1700000000000
    lines = [JTL_HEADER]
    for i in range(20):
        ts = base_ts + i * 1000  # 1 second apart -> 19s span
        label = "EndpointA" if i % 2 == 0 else "EndpointB"
        elapsed = 100 + i
        lines.append(
            f"{ts},{elapsed},{label},200,OK,Thread-1,text,true,,1000,500,1,1,http://example.com/{label},{elapsed},0,10"
        )
    with open(path, 'w') as f:
        f.write("\n".join(lines) + "\n")
    return path


class TestAnalysisAndVisualization(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_jmeter_results(self):
        with tempfile.TemporaryDirectory() as d:
            jtl = _write_jtl(d)
            result = await jmeter_server.analyze_jmeter_results(jtl, detailed=True)
            self.assertIn("Summary:", result)

    async def test_generate_visualization_types(self):
        with tempfile.TemporaryDirectory() as d:
            jtl = _write_jtl(d)

            out = os.path.join(d, "ts.png")
            result = await jmeter_server.generate_visualization(jtl, "time_series", out)
            self.assertTrue(result.startswith("Time series graph generated:"), result)
            self.assertTrue(os.path.exists(out))

            out = os.path.join(d, "cmp.png")
            result = await jmeter_server.generate_visualization(jtl, "comparison", out)
            self.assertTrue(result.startswith("Endpoint comparison chart generated:"), result)
            self.assertTrue(os.path.exists(out))

            out = os.path.join(d, "dist.png")
            result = await jmeter_server.generate_visualization(jtl, "distribution", out)
            self.assertTrue(result.startswith("Distribution graph generated:"), result)
            self.assertTrue(os.path.exists(out))

            out = os.path.join(d, "report.html")
            result = await jmeter_server.generate_visualization(jtl, "html_report", out)
            self.assertTrue(result.startswith("HTML report generated:"), result)
            self.assertTrue(os.path.exists(out))


class TestMainModule(unittest.TestCase):
    def test_main_uses_server_mcp_and_no_stdout(self):
        import main
        self.assertIs(main.mcp, jmeter_server.mcp)
        buf = io.StringIO()
        with mock.patch.object(main.mcp, 'run') as mock_run, contextlib.redirect_stdout(buf):
            main.main()
        mock_run.assert_called_once_with(transport='stdio')
        self.assertEqual(buf.getvalue(), "")

def _make_record(**kw):
    from runs.registry import RunRecord
    defaults = dict(
        run_id="run123", test_file="/tmp/t.jmx", cmd=["jmeter"], pid=4242,
        status="running", start_time="2023-01-01T00:00:00", end_time=None,
        exit_code=None, run_dir="/tmp/run", stdout_path="/tmp/o.log",
        stderr_path="/tmp/e.log", jtl_path="/tmp/r.jtl", report_dir=None,
        shutdown_port=4445, properties={})
    defaults.update(kw)
    return RunRecord(**defaults)


class TestAsyncRunTools(unittest.IsolatedAsyncioTestCase):
    def _manager(self, **kw):
        mgr = mock.MagicMock()
        mgr.start = mock.AsyncMock(return_value=_make_record(report_dir="/tmp/rep"))
        mgr.status = mock.MagicMock(return_value=_make_record())
        mgr.stop = mock.AsyncMock(return_value=_make_record(status="stopped", exit_code=-15))
        mgr.output = mock.MagicMock(return_value={"stdout": "out\n", "stderr": "err\n"})
        mgr.list = mock.MagicMock(return_value=[_make_record()])
        for k, v in kw.items():
            setattr(mgr, k, v)
        return mgr

    async def test_start_jmeter_test(self):
        mgr = self._manager()
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.start_jmeter_test("t.jmx")
        self.assertIn("Started JMeter run run123", result)
        self.assertIn("PID: 4242", result)
        self.assertIn("Report dir: /tmp/rep", result)
        self.assertIn("get_test_status('run123')", result)

    async def test_start_jmeter_test_validation_error(self):
        mgr = self._manager()
        mgr.start = mock.AsyncMock(side_effect=ValueError("Error: Test file not found: x.jmx"))
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.start_jmeter_test("x.jmx")
        self.assertEqual(result, "Error: Test file not found: x.jmx")

    async def test_get_test_status(self):
        with tempfile.TemporaryDirectory() as d:
            jtl = os.path.join(d, "r.jtl")
            with open(jtl, 'w') as f:
                f.write("timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect\n")
                f.write("1625097600000,100,EP,200,OK,T-1,text,true,,1,1,1,1,u,100,0,10\n")
            mgr = self._manager()
            mgr.status = mock.MagicMock(return_value=_make_record(jtl_path=jtl))
            with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
                result = await jmeter_server.get_test_status("run123")
        self.assertIn("Status: running", result)
        self.assertIn("Live metrics:", result)
        self.assertIn("Total samples so far: 1", result)

    async def test_get_test_status_unknown(self):
        mgr = self._manager()
        mgr.status = mock.MagicMock(return_value=None)
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.get_test_status("nope")
        self.assertEqual(result, "Error: Unknown run id")

    async def test_stop_jmeter_test(self):
        mgr = self._manager()
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.stop_jmeter_test("run123", graceful=True, timeout_seconds=5)
        mgr.stop.assert_awaited_once()
        self.assertIn("stopped", result)

    async def test_stop_not_running(self):
        mgr = self._manager()
        mgr.status = mock.MagicMock(return_value=_make_record(status="completed"))
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.stop_jmeter_test("run123")
        self.assertIn("not running", result)

    async def test_get_test_output(self):
        mgr = self._manager()
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.get_test_output("run123", tail_lines=50)
        self.assertIn("out", result)
        self.assertIn("err", result)

    async def test_list_test_runs(self):
        mgr = self._manager()
        with mock.patch('jmeter_server.get_run_manager', return_value=mgr):
            result = await jmeter_server.list_test_runs()
        self.assertIn("run123", result)
        self.assertIn("running", result)
