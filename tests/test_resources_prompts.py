"""
Tests for MCP resources and prompts using the real FastMCP instance.

This module re-imports jmeter_server with the real mcp package (the
stubbed mcp modules injected by test_jmeter_server.py are removed from
sys.modules first so a fresh real FastMCP backs the decorators).
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

_orig_modules = {}
for _mod in ['jmeter_server', 'mcp.server.fastmcp', 'mcp.server', 'mcp', 'dotenv']:
    if _mod in sys.modules:
        _orig_modules[_mod] = sys.modules.pop(_mod)
try:
    jmeter_server = importlib.import_module('jmeter_server')
finally:
    # Restore any stubbed modules so other test modules keep working
    for _mod in ['jmeter_server', 'mcp.server.fastmcp', 'mcp.server', 'mcp', 'dotenv']:
        sys.modules.pop(_mod, None)
    sys.modules.update(_orig_modules)

from runs.manager import RunManager
from runs.registry import RunRecord

HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"


def _resource_text(contents):
    return "".join(c.content for c in contents)


class TestResourcesAndPrompts(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.jtl = d / "results.jtl"
        self.jtl.write_text(HEADER + "\n" + "\n".join(
            f"{1625097600000 + i * 1000},120,EP,200,OK,T-1,text,true,,1,1,1,1,u,120,0,10"
            for i in range(5)) + "\n")
        self.stdout = d / "stdout.log"
        self.stdout.write_text("hello stdout\n")
        self.stderr = d / "stderr.log"
        self.stderr.write_text("oops stderr\n")

        self.manager = RunManager(workdir=d / "work")
        record = RunRecord(
            run_id="rid1", test_file=str(d / "t.jmx"), cmd=["jmeter"],
            pid=os.getpid(), status="running",
            start_time=datetime.now().isoformat(), end_time=None,
            exit_code=None, run_dir=str(d), stdout_path=str(self.stdout),
            stderr_path=str(self.stderr), jtl_path=str(self.jtl),
            report_dir=None, shutdown_port=4445)
        self.manager.registry.put(record)

        patcher = mock.patch.object(jmeter_server, 'get_run_manager',
                                    return_value=self.manager)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mcp = jmeter_server.mcp

    async def test_list_resources(self):
        resources = await self.mcp.list_resources()
        uris = [str(r.uri) for r in resources]
        self.assertIn("jmeter://runs", uris)

    async def test_list_resource_templates(self):
        templates = await self.mcp.list_resource_templates()
        uris = [t.uriTemplate for t in templates]
        self.assertIn("jmeter://runs/{run_id}", uris)
        self.assertIn("jmeter://runs/{run_id}/output", uris)
        self.assertIn("jmeter://runs/{run_id}/analysis", uris)

    async def test_read_runs_list(self):
        contents = await self.mcp.read_resource("jmeter://runs")
        data = json.loads(_resource_text(contents))
        self.assertEqual(data[0]["run_id"], "rid1")

    async def test_read_run_status(self):
        contents = await self.mcp.read_resource("jmeter://runs/rid1")
        data = json.loads(_resource_text(contents))
        self.assertEqual(data["run_id"], "rid1")
        self.assertEqual(data["status"], "running")
        self.assertIn("elapsed_seconds", data)
        self.assertIsNotNone(data["live_metrics"])
        self.assertEqual(data["live_metrics"]["total_samples"], 5)

    async def test_read_run_output(self):
        contents = await self.mcp.read_resource("jmeter://runs/rid1/output")
        text = _resource_text(contents)
        self.assertIn("hello stdout", text)
        self.assertIn("--- stderr ---", text)
        self.assertIn("oops stderr", text)

    async def test_read_run_analysis(self):
        contents = await self.mcp.read_resource("jmeter://runs/rid1/analysis")
        data = json.loads(_resource_text(contents))
        self.assertTrue(data["ok"])
        self.assertEqual(data["data"]["summary"]["total_samples"], 5)

    async def test_unknown_run_id_raises(self):
        with self.assertRaises(Exception):
            await self.mcp.read_resource("jmeter://runs/nope")
        with self.assertRaises(Exception):
            await self.mcp.read_resource("jmeter://runs/nope/output")

    async def test_list_prompts(self):
        prompts = await self.mcp.list_prompts()
        names = [p.name for p in prompts]
        self.assertIn("analyze_latest_run", names)
        self.assertIn("compare_last_two_runs", names)
        self.assertIn("run_and_monitor_test", names)

    async def test_get_prompt(self):
        result = await self.mcp.get_prompt("analyze_latest_run")
        text = result.messages[0].content.text
        self.assertIn("list_test_runs", text)
        self.assertIn("analyze_jmeter_results", text)
        result = await self.mcp.get_prompt("run_and_monitor_test",
                                           arguments={"test_file": "/tmp/x.jmx"})
        self.assertIn("/tmp/x.jmx", result.messages[0].content.text)


if __name__ == '__main__':
    unittest.main()
