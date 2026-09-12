"""
Tests for the run registry persistence and reconciliation.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from runs.registry import RunRecord, RunRegistry


def _record(run_id, status="completed", pid=None):
    return RunRecord(
        run_id=run_id, test_file="/tmp/t.jmx", cmd=["jmeter", "-n"],
        pid=pid, status=status, start_time=datetime.now().isoformat(),
        end_time=None, exit_code=0, run_dir="/tmp/run", stdout_path="/tmp/o",
        stderr_path="/tmp/e", jtl_path=None, report_dir=None,
        shutdown_port=4445)


class TestRunRegistry(unittest.TestCase):
    def test_roundtrip_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "runs.json"
            reg = RunRegistry(path)
            reg.put(_record("r1"))
            reg2 = RunRegistry(path)
            rec = reg2.get("r1")
            self.assertIsNotNone(rec)
            self.assertEqual(rec.run_id, "r1")
            self.assertEqual(rec.status, "completed")

    def test_corrupt_file_backed_up_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "runs.json"
            path.write_text("{ not json !")
            with self.assertLogs('runs.registry', level='WARNING'):
                reg = RunRegistry(path)
            self.assertEqual(reg.list(), [])
            self.assertTrue((Path(d) / "runs.json.corrupt").exists())

    def test_list_newest_first_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            reg = RunRegistry(Path(d) / "runs.json")
            for i in range(5):
                r = _record(f"r{i}")
                r.start_time = f"2023-01-01T00:00:0{i}"
                reg.put(r)
            runs = reg.list()
            self.assertEqual([r.run_id for r in runs], ["r4", "r3", "r2", "r1", "r0"])
            self.assertEqual(len(reg.list(limit=2)), 2)

    def test_remove(self):
        with tempfile.TemporaryDirectory() as d:
            reg = RunRegistry(Path(d) / "runs.json")
            reg.put(_record("r1"))
            reg.remove("r1")
            self.assertIsNone(reg.get("r1"))

    def test_reconcile_marks_dead_pid_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            reg = RunRegistry(Path(d) / "runs.json")
            dead = _record("dead", status="running", pid=99999999)
            dead.start_time = "2023-01-01T00:00:00"
            reg.put(dead)
            alive = _record("alive", status="running", pid=os.getpid())
            alive.start_time = "2023-01-01T00:00:01"
            reg.put(alive)
            reg.reconcile()
            self.assertEqual(reg.get("dead").status, "unknown")
            self.assertEqual(reg.get("dead").error,
                             "process not found after server restart")
            self.assertEqual(reg.get("alive").status, "running")


if __name__ == '__main__':
    unittest.main()
