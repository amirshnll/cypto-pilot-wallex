from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import fcntl
import tempfile

from django.conf import settings


@contextmanager
def paper_runtime_lock() -> Iterator[None]:
    database_name = str(settings.DATABASES["default"]["NAME"])
    directory = Path(database_name).parent
    if database_name == ":memory:" or database_name.startswith("file:"):
        directory = Path(tempfile.gettempdir())
    path = directory / "paper-runtime.lock"
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(
                "A bot cycle is running; please try again shortly."
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
