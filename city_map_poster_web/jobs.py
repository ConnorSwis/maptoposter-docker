import glob
import json
import os
import queue
import re
import threading
import time
import subprocess
import uuid
from dataclasses import dataclass, field

from .config import AppConfig


def sse(event: str, data: str) -> str:
    # SSE format: "event: <name>\ndata: <line>\n\n"
    out = []
    for line in (data or "").splitlines() or [""]:
        out.append(f"event: {event}\ndata: {line}\n\n")
    return "".join(out)


@dataclass
class Job:
    id: str
    q: "queue.Queue[str]" = field(default_factory=queue.Queue)
    done: bool = False
    ok: bool = False
    filename: str | None = None
    error: str | None = None
    stage_id: str | None = None
    stage_label: str | None = None
    created_ts: float = field(default_factory=time.time)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)


@dataclass(frozen=True)
class Stage:
    id: str
    label: str
    patterns: tuple[re.Pattern[str], ...] = ()


STAGES: tuple[Stage, ...] = (
    Stage("start", "Starting job"),
    Stage(
        "geocode",
        "Resolving location",
        (
            re.compile(r"Looking up coordinates", re.IGNORECASE),
            re.compile(r"Using cached coordinates", re.IGNORECASE),
            re.compile(r"Using custom coordinates", re.IGNORECASE),
        ),
    ),
    Stage(
        "street",
        "Downloading street network",
        (re.compile(r"Downloading street network", re.IGNORECASE),),
    ),
    Stage(
        "data",
        "Preparing map data",
        (re.compile(r"All data retrieved successfully", re.IGNORECASE),),
    ),
    Stage(
        "render",
        "Rendering map",
        (re.compile(r"Rendering map", re.IGNORECASE),),
    ),
    Stage(
        "save",
        "Saving image",
        (re.compile(r"Saving to", re.IGNORECASE),),
    ),
    Stage(
        "complete",
        "Finalizing",
        (
            re.compile(r"Done\. Poster saved as", re.IGNORECASE),
            re.compile(r"Poster generation complete", re.IGNORECASE),
        ),
    ),
)


def _send_steps(job: Job) -> None:
    payload = {
        "steps": [{"id": stage.id, "label": stage.label} for stage in STAGES],
    }
    job.q.put(sse("steps", json.dumps(payload)))


def _send_stage(job: Job, stage: Stage, index: int) -> None:
    job.stage_id = stage.id
    job.stage_label = stage.label
    payload = {
        "id": stage.id,
        "label": stage.label,
        "index": index,
        "total": len(STAGES),
    }
    job.q.put(sse("stage", json.dumps(payload)))


def run_generate_job(config: AppConfig, job: Job, cmd: list[str], logger) -> None:
    """
    Runs create_map_poster.py and pushes stage updates to job.q.
    """
    try:
        _send_steps(job)
        _send_stage(job, STAGES[0], 0)

        existing_files = set(glob.glob(os.path.join(config.poster_dir, "*.png")))

        if cmd and cmd[0] == "python":
            cmd = ["python", "-u", *cmd[1:]]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None
        current_stage_index = 0
        for line in proc.stdout:
            text = line.rstrip("\n")
            for idx in range(current_stage_index + 1, len(STAGES)):
                stage = STAGES[idx]
                if stage.patterns and any(p.search(text) for p in stage.patterns):
                    _send_stage(job, stage, idx)
                    current_stage_index = idx
                    break

        rc = proc.wait()

        if rc != 0:
            job.ok = False
            job.error = f"Poster command failed (exit code {rc})"
            return

        current_files = set(glob.glob(os.path.join(config.poster_dir, "*.png")))
        new_files = list(current_files - existing_files)

        if new_files:
            latest_file = max(new_files, key=os.path.getctime)
            job.filename = os.path.basename(latest_file)
            job.ok = True
            if current_stage_index < len(STAGES) - 1:
                _send_stage(job, STAGES[-1], len(STAGES) - 1)
            job.q.put(sse("done", job.filename))
        else:
            job.ok = False
            job.error = "Script finished but no image file found."
            job.q.put(sse("error", job.error))

    except Exception as e:
        job.ok = False
        job.error = str(e)
        job.q.put(sse("error", job.error))
    finally:
        job.done = True
        job.q.put(sse("end", ""))
        job.q.put("")  # raw sentinel to stop SSE generator
