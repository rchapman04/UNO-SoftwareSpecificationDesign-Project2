"""Archiver.

Architecture: may depend on Audit Log. Scheduled monthly/daily (Azure timer
trigger, not yet wired). Serves: FR-009, NFR-001.

Blob client is injected as BlobArchive (not yet chosen).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.audit_log import AuditLog


class BlobArchive(Protocol):
    def write_worm(self, key: str, payload: bytes, retain_until: datetime) -> str:
        """Write an immutable object. Returns the archive reference."""
        ...


@dataclass(frozen=True)
class ArchiveRun:
    cutoff: datetime
    archived_count: int
    archive_refs: tuple[str, ...]
    completed_at: datetime


@dataclass
class Archiver:
    audit_log: AuditLog
    blob: BlobArchive | None
    now: Callable[[], datetime]
    archive_after: timedelta = timedelta(days=365)  # FR-009: older than 1 year
    retention_years: int = 7                        # FR-009: keep 7 years

    def run_archive(self, cutoff: datetime | None) -> ArchiveRun:
        raise NotImplementedError("Archiver.run_archive is not implemented")
