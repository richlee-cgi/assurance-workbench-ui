import time

from app.evidence import EvidenceForm
from app.jobs import EvidenceJob, JOBS, JOBS_LOCK, cancel_job, start_evidence_pack_job
from app.settings import AppSettings


class FakeProcess:
    def __init__(self, command, stdout=None, stderr=None, exit_code=0):
        self.command = command
        self.stdout = stdout or []
        self.stderr = stderr or []
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def test_start_evidence_pack_job_streams_logs(tmp_path) -> None:
    processes = []

    def fake_popen(command, **kwargs):
        process = FakeProcess(command, stdout=["started\n", "done\n"], stderr=["warn\n"])
        processes.append(process)
        return process

    job = start_evidence_pack_job(
        EvidenceForm(topic="booking"),
        AppSettings(assurance_path="/tmp/assurance", workbench_root=str(tmp_path)),
        popen=fake_popen,
    )

    _wait_for_exit(job)

    assert job.exit_code == 0
    assert job.stdout == "started\ndone\n"
    assert job.stderr == "warn\n"
    assert (job.run_dir / "stdout.log").read_text(encoding="utf-8") == "started\ndone\n"
    assert (job.run_dir / "stderr.log").read_text(encoding="utf-8") == "warn\n"
    assert (job.run_dir / "exit-code.txt").read_text(encoding="utf-8") == "0\n"
    assert processes[0].command[-2] == "--out"


def test_cancel_job_terminates_running_process(tmp_path) -> None:
    process = FakeProcess(["assurance"], exit_code=130)
    job = EvidenceJob(
        id="job-cancel",
        run_dir=tmp_path,
        command=["assurance"],
        evidence_path=tmp_path / "evidence-pack.md",
        process=process,
    )
    with JOBS_LOCK:
        JOBS[job.id] = job

    canceled = cancel_job(job.id)

    assert canceled is job
    assert job.canceled is True
    assert process.terminated is True


def _wait_for_exit(job: EvidenceJob) -> None:
    deadline = time.time() + 2
    while time.time() < deadline:
        if job.exit_code is not None and "done" in job.stdout and "warn" in job.stderr:
            return
        time.sleep(0.01)
    raise AssertionError("job did not finish")
