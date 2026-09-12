"""
Run manager for long-running JMeter executions.

Spawns JMeter as a detached async subprocess, tracks it in the persistent
RunRegistry, and supports status polling, graceful shutdown (JMeter's
non-GUI UDP shutdown listener), forced stop, and output retrieval.
"""

import asyncio
import logging
import os
import signal
import socket
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from runs.registry import RunRecord, RunRegistry
from runs.util import (build_jmeter_command, generate_unique_id,
                       kill_process_tree, truncate_output)

logger = logging.getLogger(__name__)


def _default_workdir() -> Path:
    return Path(os.getenv('JMETER_MCP_WORKDIR', str(Path.home() / '.jmeter-mcp')))


def _free_udp_port() -> int:
    """Pick a free UDP port for JMeter's non-GUI shutdown listener.

    JMeter only attempts to bind the listener for ports in
    [jmeterengine.nongui.port, 4455] (it scans upward to a hard max of
    4455), so a randomly assigned high port would silently fail — probe
    4445..4455 and return the first free one, else 4445 (letting JMeter
    do its own upward scan)."""
    for port in range(4445, 4456):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(('127.0.0.1', port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    return 4445


def _pid_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class RunManager:
    """Manages asynchronous JMeter runs."""

    def __init__(self, workdir: Optional[Path] = None,
                 shutdown_port_provider: Optional[Callable[[], int]] = None) -> None:
        self.workdir = Path(workdir) if workdir else _default_workdir()
        self.registry = RunRegistry(self.workdir / 'runs.json')
        self._shutdown_port_provider = shutdown_port_provider or _free_udp_port
        self._tasks: Dict[str, asyncio.Task] = {}
        self._procs: Dict[str, asyncio.subprocess.Process] = {}

    async def start(self, test_file: str, properties: Optional[Dict] = None,
                    generate_report: bool = False,
                    report_output_dir: Optional[str] = None,
                    log_file: Optional[str] = None) -> RunRecord:
        """Start a JMeter run in the background and return its record."""
        test_file_path = Path(test_file).resolve()

        if not test_file_path.exists():
            raise ValueError(f"Error: Test file not found: {test_file}")
        if not test_file_path.suffix == '.jmx':
            raise ValueError(f"Error: Invalid file type. Expected .jmx file: {test_file}")

        jmeter_bin = os.getenv('JMETER_BIN', 'jmeter')
        run_id = generate_unique_id()
        run_dir = self.workdir / 'runs' / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        stdout_path = run_dir / 'stdout.log'
        stderr_path = run_dir / 'stderr.log'
        jtl_path = Path(log_file).resolve() if log_file else run_dir / 'results.jtl'
        shutdown_port = self._shutdown_port_provider()

        if generate_report and not report_output_dir:
            # Default report location inside the run directory; appended
            # manually so it stays exactly <run_dir>/report.
            cmd, jtl_resolved, _ = build_jmeter_command(
                test_file_path, jmeter_bin, True, properties,
                generate_report=False, log_file=str(jtl_path))
            report_dir = str(run_dir / 'report')
            cmd.extend(['-e', '-o', report_dir])
        else:
            cmd, jtl_resolved, report_dir = build_jmeter_command(
                test_file_path, jmeter_bin, True, properties,
                generate_report=generate_report,
                report_output_dir=report_output_dir,
                log_file=str(jtl_path))
        if jtl_resolved:
            jtl_path = Path(jtl_resolved)

        cmd.append(f'-Jjmeterengine.nongui.port={shutdown_port}')

        record = RunRecord(
            run_id=run_id,
            test_file=str(test_file_path),
            cmd=cmd,
            pid=None,
            status="starting",
            start_time=datetime.now().isoformat(),
            end_time=None,
            exit_code=None,
            run_dir=str(run_dir),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            jtl_path=str(jtl_path),
            report_dir=report_dir,
            shutdown_port=shutdown_port,
            properties={k: str(v) for k, v in (properties or {}).items()},
        )
        self.registry.put(record)

        stdout_f = open(stdout_path, 'wb')
        stderr_f = open(stderr_path, 'wb')
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=stderr_f,
                start_new_session=True
            )
        finally:
            stdout_f.close()
            stderr_f.close()

        record.pid = proc.pid
        record.status = "running"
        self.registry.put(record)
        self._procs[run_id] = proc
        self._tasks[run_id] = asyncio.create_task(self._wait(run_id, proc))
        return record

    async def _wait(self, run_id: str, proc) -> None:
        rc = await proc.wait()
        record = self.registry.get(run_id)
        if record is None:
            return
        record.exit_code = rc
        record.end_time = datetime.now().isoformat()
        if record.stop_requested:
            record.status = "stopped"
        else:
            record.status = "completed" if rc == 0 else "failed"
        self.registry.put(record)

    def status(self, run_id: str) -> Optional[RunRecord]:
        record = self.registry.get(run_id)
        if record is None:
            return None
        if record.status in ("starting", "running") and run_id not in self._tasks:
            # Process was spawned before a server restart
            if not _pid_alive(record.pid):
                record.status = "unknown"
                record.error = "process not found after server restart"
                record.end_time = datetime.now().isoformat()
                self.registry.put(record)
        return record

    async def stop(self, run_id: str, graceful: bool = True,
                   timeout_seconds: float = 30.0) -> Optional[RunRecord]:
        record = self.registry.get(run_id)
        if record is None or record.status not in ("starting", "running"):
            return record

        record.stop_requested = True
        self.registry.put(record)
        proc = self._procs.get(run_id)

        if graceful:
            # Ask JMeter's non-GUI shutdown listener to stop the test
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.sendto(b"Shutdown", ('127.0.0.1', record.shutdown_port))
                finally:
                    sock.close()
            except OSError as e:
                logger.warning(f"Failed to send shutdown datagram for run {run_id}: {e}")
            if not await self._wait_for_exit(run_id, proc, timeout_seconds):
                # Graceful shutdown didn't take; escalate
                if proc is not None and proc.returncode is None:
                    kill_process_tree(proc.pid, signal.SIGTERM)
                if not await self._wait_for_exit(run_id, proc, 5.0):
                    if proc is not None and proc.returncode is None:
                        kill_process_tree(proc.pid, signal.SIGKILL)
                    await self._wait_for_exit(run_id, proc, 5.0)
        else:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.sendto(b"StopTestNow", ('127.0.0.1', record.shutdown_port))
                finally:
                    sock.close()
            except OSError as e:
                logger.warning(f"Failed to send StopTestNow datagram for run {run_id}: {e}")
            if not await self._wait_for_exit(run_id, proc, 5.0):
                if proc is not None and proc.returncode is None:
                    kill_process_tree(proc.pid, signal.SIGKILL)
                await self._wait_for_exit(run_id, proc, 5.0)

        # Fall back to direct liveness check if we have no local proc handle
        if proc is None and record.pid and _pid_alive(record.pid):
            kill_process_tree(record.pid, signal.SIGKILL)

        record = self.registry.get(run_id)
        if record is not None and record.status in ("starting", "running"):
            record.status = "stopped"
            record.end_time = datetime.now().isoformat()
            self.registry.put(record)
        return record

    async def _wait_for_exit(self, run_id: str, proc, timeout: float) -> bool:
        task = self._tasks.get(run_id)
        try:
            if task is not None:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            elif proc is not None:
                await asyncio.wait_for(proc.wait(), timeout=timeout)
            else:
                # No local handle: poll the pid
                record = self.registry.get(run_id)
                deadline = asyncio.get_event_loop().time() + timeout
                while record and record.pid and _pid_alive(record.pid):
                    if asyncio.get_event_loop().time() >= deadline:
                        return False
                    await asyncio.sleep(0.1)
                return True
            return True
        except asyncio.TimeoutError:
            return False

    def output(self, run_id: str, tail_lines: int = 100) -> Dict[str, str]:
        record = self.registry.get(run_id)
        if record is None:
            return {"stdout": "", "stderr": ""}
        result = {}
        for name, path in (("stdout", record.stdout_path), ("stderr", record.stderr_path)):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    result[name] = truncate_output(f.read(), max_lines=tail_lines)
            except OSError:
                result[name] = ""
        return result

    def list(self, limit: int = 20) -> List[RunRecord]:
        records = self.registry.list(limit=limit)
        for record in records:
            if record.status in ("starting", "running"):
                self.status(record.run_id)  # refresh liveness
        return self.registry.list(limit=limit)


_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    """Lazily build the shared RunManager and reconcile dead runs once."""
    global _manager
    if _manager is None:
        _manager = RunManager()
        try:
            _manager.registry.reconcile()
        except Exception as e:
            logger.warning(f"Failed to reconcile run registry: {e}")
    return _manager
