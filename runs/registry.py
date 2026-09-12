"""
Persistent registry of JMeter runs.

Stores run records in a JSON file so runs can be tracked across tool
calls and reconciled after a server restart.
"""

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# RunStatus values: "starting", "running", "completed", "failed",
# "timed_out", "stopped", "unknown"


@dataclass
class RunRecord:
    """Persistent record of a single JMeter run."""

    run_id: str
    test_file: str
    cmd: List[str]
    pid: Optional[int]
    status: str
    start_time: str  # isoformat
    end_time: Optional[str]
    exit_code: Optional[int]
    run_dir: str
    stdout_path: str
    stderr_path: str
    jtl_path: Optional[str]
    report_dir: Optional[str]
    shutdown_port: int
    properties: Dict[str, str] = field(default_factory=dict)
    stop_requested: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> "RunRecord":
        known = {f for f in RunRecord.__dataclass_fields__}
        return RunRecord(**{k: v for k, v in data.items() if k in known})


class RunRegistry:
    """JSON-file-backed registry of RunRecords."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._records: Dict[str, RunRecord] = {}
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for run_id, record in data.items():
                    self._records[run_id] = RunRecord.from_dict(record)
            except Exception as e:
                logger.warning(f"Corrupt run registry at {self.path}: {e}; starting empty")
                try:
                    shutil.copy2(self.path, self.path.with_suffix(self.path.suffix + '.corrupt'))
                except OSError:
                    pass
                self._records = {}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + '.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump({k: r.to_dict() for k, r in self._records.items()}, f, indent=2)
        os.replace(tmp_path, self.path)

    def get(self, run_id: str) -> Optional[RunRecord]:
        return self._records.get(run_id)

    def put(self, record: RunRecord) -> None:
        self._records[record.run_id] = record
        self._persist()

    def list(self, limit: Optional[int] = None) -> List[RunRecord]:
        records = sorted(self._records.values(), key=lambda r: r.start_time, reverse=True)
        return records[:limit] if limit else records

    def remove(self, run_id: str) -> None:
        if run_id in self._records:
            del self._records[run_id]
            self._persist()

    def reconcile(self) -> None:
        """Mark records left in starting/running state whose processes are
        dead (e.g. after a server restart) as unknown."""
        changed = False
        for record in self._records.values():
            if record.status in ("starting", "running"):
                alive = False
                if record.pid:
                    try:
                        os.kill(record.pid, 0)
                        alive = True
                    except ProcessLookupError:
                        alive = False
                    except PermissionError:
                        alive = True
                if not alive:
                    record.status = "unknown"
                    record.error = "process not found after server restart"
                    record.end_time = datetime.now().isoformat()
                    changed = True
        if changed:
            self._persist()
