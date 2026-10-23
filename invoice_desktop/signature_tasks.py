"""Tk-free, serial background work for one signature manager."""

from io import BytesIO
import os
from queue import Empty, Queue
from threading import Event, Lock, Thread

from PIL import Image


class SignatureRefreshError(ValueError):
    """A mutation saved successfully, but its following library read failed."""


class SignatureTasks:
    """The daemon retains only the store and plain requests, never UI callbacks."""

    def __init__(self, store):
        self.store = store
        self.jobs = Queue()
        self.results = Queue()
        self.closed = Event()
        self.serial = 0
        self.preview_id = None
        self.preview_job = None
        self.preview_queued = False
        self.role_preview_id = None
        self.role_preview_job = None
        self.role_preview_queued = False
        self.preview_lock = Lock()
        Thread(target=self._work, name="signature-library", daemon=True).start()

    def submit(self, kind, *args, **kwargs):
        self.serial += 1
        request_id = self.serial
        job = (request_id, kind, args, kwargs)
        if kind == "preview":
            with self.preview_lock:
                self.preview_id = request_id
                self.preview_job = job
                if not self.preview_queued:
                    self.preview_queued = True
                    self.jobs.put("preview")
        elif kind == "role_previews":
            with self.preview_lock:
                self.role_preview_id = request_id
                self.role_preview_job = job
                if not self.role_preview_queued:
                    self.role_preview_queued = True
                    self.jobs.put("role_previews")
        else:
            self.jobs.put(job)
        return request_id

    def cancel_preview(self):
        with self.preview_lock:
            self.preview_id = None
            self.preview_job = None

    def close(self):
        self.closed.set()
        self.cancel_preview()
        self.cancel_role_previews()
        for queue in (self.jobs, self.results):
            while True:
                try:
                    queue.get_nowait()
                except Empty:
                    break
        self.jobs.put(None)

    def _work(self):
        while not self.closed.is_set():
            job = self.jobs.get()
            if job is None or self.closed.is_set():
                return
            if job == "preview":
                with self.preview_lock:
                    job = self.preview_job
                    self.preview_job = None
                    self.preview_queued = False
                if job is None:
                    continue
            elif job == "role_previews":
                with self.preview_lock:
                    job = self.role_preview_job
                    self.role_preview_job = None
                    self.role_preview_queued = False
                if job is None:
                    continue
            request_id, kind, args, kwargs = job
            if kind == "preview" and not self._current_preview(request_id):
                continue
            if kind == "role_previews" and not self._current_role_preview(request_id):
                continue
            try:
                value = (self._perform_role_previews(request_id, *args) if kind == "role_previews"
                         else self._perform(kind, args, kwargs))
                error = None
            except Exception as exc:
                value, error = None, exc
            if (not self.closed.is_set()
                    and (kind != "preview" or self._current_preview(request_id))
                    and (kind != "role_previews" or self._current_role_preview(request_id))):
                self.results.put((request_id, kind, value, error))

    def _current_preview(self, request_id):
        with self.preview_lock:
            return request_id == self.preview_id

    def cancel_role_previews(self):
        with self.preview_lock:
            self.role_preview_id = None
            self.role_preview_job = None

    def _current_role_preview(self, request_id):
        with self.preview_lock:
            return request_id == self.role_preview_id

    def _perform_role_previews(self, request_id, item_ids, revision):
        previews = {}
        for item_id in dict.fromkeys(item_ids):
            if self.closed.is_set() or not self._current_role_preview(request_id):
                break
            try:
                raw = self.store.image_bytes(item_id, expected_revision=revision, size=(200, 90))
                with Image.open(BytesIO(raw)) as source:
                    previews[item_id] = (source.convert("RGBA"), None)
            except Exception as exc:
                previews[item_id] = (None, str(exc))
        return previews

    def _perform(self, kind, args, kwargs):
        if kind == "preview":
            item_id, revision = args
            raw = self.store.image_bytes(item_id, expected_revision=revision, size=(280, 180))
            with Image.open(BytesIO(raw)) as source:
                return source.convert("RGBA")
        if kind == "mutate":
            method, *arguments = args
            result = getattr(self.store, method)(*arguments, **kwargs)
            try:
                data = self.store.read()
            except Exception as exc:
                raise SignatureRefreshError("签名修改已保存，但列表刷新失败。请刷新列表核对当前角色设置。") from exc
            return data, result
        data = self.store.read()
        if kind == "folder":
            os.startfile(self.store.image_dir)
        return data
