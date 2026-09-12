"""
Tests for RunManager using a fake jmeter shell script.

The fake jmeter echoes its argv, appends a CSV row to the -l JTL every
0.2s, runs for N seconds (from -Jduration=N), and exits with the code
from -Jexitcode=N (default 0).
"""

import asyncio
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from runs.manager import RunManager

FAKE_JMETER = r"""#!/bin/sh
echo "argv: $@"
jtl=""; dur=30; code=0; prev=""
for a in "$@"; do
  case "$prev" in -l) jtl="$a";; esac
  prev="$a"
done
for a in "$@"; do
  case "$a" in
    -Jduration=*) dur=${a#-Jduration=} ;;
    -Jexitcode=*) code=${a#-Jexitcode=} ;;
  esac
done
if [ -n "$jtl" ]; then
  echo "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect" > "$jtl"
fi
i=0
while [ $i -lt $((dur * 5)) ]; do
  if [ -n "$jtl" ]; then
    ts=$(( $(date +%s) * 1000 + i ))
    echo "$ts,123,EP,200,OK,T-1,text,true,,1000,500,2,2,http://x,123,0,10" >> "$jtl"
  fi
  sleep 0.2
  i=$((i + 1))
done
exit $code
"""


class RunManagerTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.fake = d / "jmeter"
        self.fake.write_text(FAKE_JMETER)
        os.chmod(self.fake, 0o755)
        self.test_file = d / "test.jmx"
        self.test_file.write_text("<jmeterTestPlan/>")
        self.workdir = d / "work"
        self.env = mock.patch.dict(os.environ, {
            'JMETER_BIN': str(self.fake),
            'JMETER_MCP_WORKDIR': str(self.workdir),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.manager = RunManager(workdir=self.workdir)
        self.addAsyncCleanup(self._cleanup_tasks)

    async def _cleanup_tasks(self):
        for run_id, proc in list(self.manager._procs.items()):
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        for task in self.manager._tasks.values():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except Exception:
                pass

    def _started(self, record):
        self.assertEqual(record.status, "running")
        self.assertTrue(record.pid)


class TestRunManager(RunManagerTestBase):
    async def test_start_and_complete(self):
        record = await self.manager.start(str(self.test_file),
                                          properties={"duration": "1"})
        self._started(record)
        self.assertEqual(record.shutdown_port and record.shutdown_port > 0, True)
        await asyncio.wait_for(self.manager._tasks[record.run_id], timeout=10)
        rec = self.manager.status(record.run_id)
        self.assertEqual(rec.status, "completed")
        self.assertEqual(rec.exit_code, 0)
        stdout = Path(rec.stdout_path).read_text()
        self.assertIn('-Jjmeterengine.nongui.port=', stdout)

    async def test_failure_exit_code(self):
        record = await self.manager.start(str(self.test_file),
                                          properties={"duration": "1", "exitcode": "2"})
        await asyncio.wait_for(self.manager._tasks[record.run_id], timeout=10)
        rec = self.manager.status(record.run_id)
        self.assertEqual(rec.status, "failed")
        self.assertEqual(rec.exit_code, 2)

    async def test_jtl_written_and_live_metrics(self):
        from runs.live_metrics import read_live_metrics
        record = await self.manager.start(str(self.test_file),
                                          properties={"duration": "3"})
        # let a few samples be written
        deadline = time.time() + 5
        while time.time() < deadline:
            m = read_live_metrics(record.jtl_path)
            if m.get("supported") and m["total_samples"] > 0:
                break
            await asyncio.sleep(0.3)
        m = read_live_metrics(record.jtl_path)
        self.assertTrue(m["supported"])
        self.assertGreater(m["total_samples"], 0)

    async def test_output_and_list(self):
        record = await self.manager.start(str(self.test_file),
                                          properties={"duration": "1"})
        await asyncio.wait_for(self.manager._tasks[record.run_id], timeout=10)
        out = self.manager.output(record.run_id)
        self.assertIn('argv:', out['stdout'])
        runs = self.manager.list()
        self.assertEqual(runs[0].run_id, record.run_id)

    async def test_validation_errors(self):
        with self.assertRaises(ValueError) as cm:
            await self.manager.start("/nonexistent/t.jmx")
        self.assertIn("Test file not found", str(cm.exception))
        bad = Path(self.tmp.name) / "bad.txt"
        bad.write_text("x")
        with self.assertRaises(ValueError):
            await self.manager.start(str(bad))

    async def test_stop_graceful_sends_shutdown_then_escalates(self):
        # Pin the shutdown port to a UDP socket this test listens on
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        self.addCleanup(listener.close)

        mgr = RunManager(workdir=self.workdir,
                         shutdown_port_provider=lambda: port)
        self.manager._procs.update(mgr._procs)
        self.manager._tasks.update(mgr._tasks)
        record = await mgr.start(str(self.test_file),
                                 properties={"duration": "30"})
        self.manager._procs[record.run_id] = mgr._procs[record.run_id]
        self.manager._tasks[record.run_id] = mgr._tasks[record.run_id]

        listener.setblocking(False)
        rec = await mgr.stop(record.run_id, graceful=True, timeout_seconds=1.0)
        # The fake ignores the datagram; SIGTERM fallback must kill it
        self.assertEqual(rec.status, "stopped")
        await asyncio.wait_for(mgr._tasks[record.run_id], timeout=10)
        try:
            data, _ = listener.recvfrom(64)
            self.assertEqual(data, b"Shutdown")
        except BlockingIOError:
            self.fail("no shutdown datagram received")

    async def test_stop_not_running_returns_record(self):
        record = await self.manager.start(str(self.test_file),
                                          properties={"duration": "1"})
        await asyncio.wait_for(self.manager._tasks[record.run_id], timeout=10)
        rec = await self.manager.stop(record.run_id)
        self.assertEqual(rec.status, "completed")

    async def test_status_unknown_after_restart(self):
        # Simulate a run record for a dead process with a fresh manager
        record = await self.manager.start(str(self.test_file),
                                          properties={"duration": "30"})
        proc = self.manager._procs[record.run_id]
        proc.kill()
        await asyncio.wait_for(self.manager._tasks[record.run_id], timeout=10)
        # Fresh manager with no task handles -> reconciles liveness
        mgr2 = RunManager(workdir=self.workdir)
        rec = mgr2.status(record.run_id)
        # record was already marked by _wait (failed, rc != 0); force a
        # stale running record to exercise the liveness path
        rec.status = "running"
        mgr2.registry.put(rec)
        rec = mgr2.status(record.run_id)
        self.assertEqual(rec.status, "unknown")


if __name__ == '__main__':
    unittest.main()
