"""
Shared utilities for run management and JMeter command construction.
"""

import datetime
import os
import signal
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_OUTPUT_MAX_LINES = 200


def generate_unique_id() -> str:
    """Generate a unique identifier using timestamp and UUID."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for brevity
    return f"{timestamp}_{random_id}"


def kill_process_tree(pid: int, sig: int = signal.SIGKILL) -> None:
    """Kill a process and its whole process group. On posix the process is
    expected to have been spawned with start_new_session=True so that its
    PID is also its process group ID (the jmeter launcher shell script
    does not reliably forward signals to the Java child)."""
    try:
        if os.name == 'posix':
            os.killpg(pid, sig)
        else:
            os.kill(pid, sig)
    except ProcessLookupError:
        pass


def truncate_output(text: str, max_lines: Optional[int] = None) -> str:
    """Truncate text to the last max_lines lines, noting how many were omitted."""
    if not text:
        return ""
    if max_lines is None:
        raw = os.getenv('JMETER_OUTPUT_MAX_LINES')
        try:
            max_lines = int(raw) if raw is not None else DEFAULT_OUTPUT_MAX_LINES
        except ValueError:
            max_lines = DEFAULT_OUTPUT_MAX_LINES
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    omitted = len(lines) - max_lines
    return f"[... {omitted} earlier lines omitted; see jmeter.log for full output ...]\n" + "\n".join(lines[-max_lines:])


def build_jmeter_command(test_file_path: Path, jmeter_bin: str, non_gui: bool = True,
                         properties: Optional[Dict] = None, generate_report: bool = False,
                         report_output_dir: Optional[str] = None,
                         log_file: Optional[str] = None) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Build the JMeter command line.

    Returns:
        (cmd, log_file, report_output_dir) — the argv list plus the
        resolved log file and report output dir (which may have been
        generated/uniquified).
    """
    cmd = [str(Path(jmeter_bin).resolve())]

    if non_gui:
        cmd.extend(['-n'])
    cmd.extend(['-t', str(test_file_path)])

    # Add JMeter properties if provided
    if properties:
        for prop_name, prop_value in properties.items():
            cmd.extend([f'-J{prop_name}={prop_value}'])

    # In non-GUI mode, always honor an explicit log file; when a report
    # is requested without one, generate a unique name
    if non_gui and log_file is None and generate_report:
        unique_id = generate_unique_id()
        log_file = f"{test_file_path.stem}_{unique_id}_results.jtl"

    if non_gui and log_file:
        cmd.extend(['-l', log_file])

    # Add report generation options if requested
    if generate_report and non_gui:
        cmd.extend(['-e'])

        # Always ensure report_output_dir is unique
        unique_id = unique_id if 'unique_id' in locals() else generate_unique_id()

        if report_output_dir:
            # Append unique identifier to user-provided report directory
            original_dir = report_output_dir
            report_output_dir = f"{original_dir}_{unique_id}"
        else:
            # Generate unique report output directory if not specified
            report_output_dir = f"{test_file_path.stem}_{unique_id}_report"

        cmd.extend(['-o', report_output_dir])

    return cmd, log_file, report_output_dir
