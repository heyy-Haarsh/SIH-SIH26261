"""
Local synchronous job runner.

Celery/Redis can replace this later when USE_CELERY=true. For the first demo,
validation runs inline in the API process.
"""

from __future__ import annotations

from typing import Callable


def enqueue(task_name: str, fn: Callable, *args, **kwargs):
    """Execute immediately when Celery is not configured."""
    return {
        "task": task_name,
        "mode": "local_sync",
        "result": fn(*args, **kwargs),
    }
