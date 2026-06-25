from __future__ import annotations

import json
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from app.evidence import EvidenceForm, build_run_command, create_run_dir, shell_command
from app.settings import AppSettings


PopenFactory = Callable[..., subprocess.Popen]


@dataclass
class EvidenceJob:
    id: str
    run_dir: Path
    command: list[str]
    evidence_path: Path
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    canceled: bool = False
    timed_out: bool = False
    process: subprocess.Popen | None = field(default=None, repr=False)

    @property
    def running(self) -> bool:
        return self.exit_code is None


JOBS: dict[str, EvidenceJob] = {}
JOBS_LOCK = threading.Lock()


def start_evidence_pack_job(
    form: EvidenceForm,
    settings: AppSettings,
    *,
    timeout: int = 300,
    popen: PopenFactory = subprocess.Popen,
) -> EvidenceJob:
    run_dir = create_run_dir(settings.workbench_root, form)
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = run_dir / "evidence-pack.md"
    command = build_run_command(form, assurance_path=settings.assurance_path, evidence_path=evidence_path)
    (run_dir / "request.json").write_text(json.dumps(asdict(form), indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "command.txt").write_text(shell_command(command) + "\n", encoding="utf-8")
    job = EvidenceJob(id=uuid.uuid4().hex, run_dir=run_dir, command=command, evidence_path=evidence_path)
    process = popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    job.process = process
    with JOBS_LOCK:
        JOBS[job.id] = job
    threading.Thread(target=_read_stream, args=(job, "stdout", process.stdout, run_dir / "stdout.log"), daemon=True).start()
    threading.Thread(target=_read_stream, args=(job, "stderr", process.stderr, run_dir / "stderr.log"), daemon=True).start()
    threading.Thread(target=_watch_process, args=(job, process, timeout), daemon=True).start()
    return job


def get_job(job_id: str) -> EvidenceJob | None:
    with JOBS_LOCK:
        return JOBS.get(job_id)


def cancel_job(job_id: str) -> EvidenceJob | None:
    job = get_job(job_id)
    if not job or not job.running or not job.process:
        return job
    job.canceled = True
    job.process.terminate()
    return job


def _read_stream(job: EvidenceJob, name: str, stream, path: Path) -> None:
    if stream is None:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8") as handle:
        for line in stream:
            current = getattr(job, name)
            setattr(job, name, current + line)
            handle.write(line)
            handle.flush()


def _watch_process(job: EvidenceJob, process: subprocess.Popen, timeout: int) -> None:
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        job.timed_out = True
        process.kill()
        exit_code = 124
    if job.canceled and exit_code == 0:
        exit_code = 130
    job.exit_code = int(exit_code)
    (job.run_dir / "exit-code.txt").write_text(str(job.exit_code) + "\n", encoding="utf-8")
