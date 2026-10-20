from dataclasses import dataclass
from typing import Literal




JobOutcome = Literal["success", "failed", "blocked", "not_modified", "disabled", "stale"]
TargetAction = Literal["complete", "retry", "block", "disable"]


@dataclass(frozen=True, slots=True)
class JobResult:
    target_id: int
    outcome: JobOutcome
    attempt_id: int | None = None
    http_status: int | None = None
    documents_saved: int = 0
    documents_skipped: int = 0
    links_discovered: int = 0
    links_enqueued: int = 0
    message: str = ""
    duration_seconds: float = 0.0