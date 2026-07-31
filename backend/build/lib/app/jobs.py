from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4


@dataclass
class RenderJob:
    status: str = "queued"
    audio: bytes | None = None
    error: str | None = None


class RenderJobs:
    """Small in-process job queue for non-blocking offline audio renders."""

    def __init__(self) -> None:
        self._jobs: dict[str, RenderJob] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="render")

    def submit(self, work: callable) -> str:
        job_id = str(uuid4())
        with self._lock:
            self._jobs[job_id] = RenderJob()
        self._executor.submit(self._run, job_id, work)
        return job_id

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job_id: str, work: callable) -> None:
        with self._lock:
            self._jobs[job_id].status = "running"
        try:
            audio = work()
        except Exception as error:  # The worker must expose failures to the job API.
            with self._lock:
                self._jobs[job_id].status = "failed"
                self._jobs[job_id].error = str(error)
        else:
            with self._lock:
                self._jobs[job_id].status = "completed"
                self._jobs[job_id].audio = audio
