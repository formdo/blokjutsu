"""Background job queue. One daemon thread owns the pipeline; Qt signals carry results to the GUI thread."""
from __future__ import annotations

import logging
import queue
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from . import store
from .backend import CaptionHeadMissing, Cancelled, ModelNotDownloaded

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    id: int
    params: object
    out_dir: Path
    preview: bool = True
    embed: bool = False              # settings inside the PNG (off unless the user turned it on)


@dataclass(frozen=True)
class DescribeJob:
    id: int
    model: str
    image: Path | None               # None with a request: Enhance Prompt
    thinking: bool = False
    request: str | None = None


def to_qimage(rgb):
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


class Worker(QObject):
    stage = Signal(int, str, int)        # job id, stage name, total steps
    step = Signal(int, int, int)         # job id, done, total
    finished = Signal(int, object)       # job id, store.Entry
    failed = Signal(int, str)
    cancelled = Signal(int)
    preview = Signal(int, QImage, bool)      # job id, image, exact (VAE) rather than approximate
    described = Signal(int, object)          # job id, {'short', 'medium', 'long'}
    missing = Signal(int, str)               # job id, 'model' or 'caption': a download is needed first

    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.jobs = queue.Queue()
        self.cancelled_ids = set()
        self.lock = threading.Lock()
        self.current = None
        threading.Thread(target=self._run, daemon=True, name="moss-worker").start()

    def submit(self, job):
        self.jobs.put(job)

    def cancel(self, job_id):
        with self.lock:
            self.cancelled_ids.add(job_id)

    def busy(self):
        return self.current is not None or not self.jobs.empty()

    def _is_cancelled(self, job_id):
        with self.lock:
            return job_id in self.cancelled_ids

    def _run(self):
        while True:
            job = self.jobs.get()
            if self._is_cancelled(job.id):
                self.cancelled.emit(job.id)
                continue
            self.current = job.id
            try:
                if isinstance(job, DescribeJob):
                    self.described.emit(job.id, self.backend.describe(
                        job.model, job.image, job.thinking,
                        on_stage=lambda s, n, j=job.id: self.stage.emit(j, s, n),
                        on_token=lambda k, n, j=job.id: self.step.emit(j, k, n),
                        cancelled=lambda j=job.id: self._is_cancelled(j), request=job.request))
                    continue
                image, meta = self.backend.generate(
                    job.params,
                    on_stage=lambda s, n, j=job.id: self.stage.emit(j, s, n),
                    on_step=lambda k, n, j=job.id: self.step.emit(j, k, n),
                    cancelled=lambda j=job.id: self._is_cancelled(j),
                    on_preview=((lambda rgb, exact, j=job.id: self.preview.emit(j, to_qimage(rgb), exact))
                                if job.preview else None),
                )
                self.stage.emit(job.id, "save", 0)
                self.finished.emit(job.id, store.save(job.out_dir, job.params, image, job.embed, **meta))
            except Cancelled:
                self.cancelled.emit(job.id)
            except ModelNotDownloaded:
                self.missing.emit(job.id, "model")
            except CaptionHeadMissing:
                self.missing.emit(job.id, "caption")
            except Exception as exc:  # surfaced in the job's card
                log.error("job %d failed\n%s", job.id, traceback.format_exc())
                self.failed.emit(job.id, f"{type(exc).__name__}: {exc}")
            finally:
                self.current = None
