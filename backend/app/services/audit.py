from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.models import AuditEvent
from app.repositories.identity import IdentityRepository


@dataclass(frozen=True)
class RequestContext:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    ip: str | None = None
    user_agent: str | None = None


class AuditService:
    def __init__(self, repo: IdentityRepository, context: RequestContext):
        self.repo, self.context = repo, context

    def record(
        self,
        action: str,
        actor_id: UUID | None,
        entity_type: str,
        entity_id: UUID | None = None,
        *,
        lab: UUID | None = None,
        before: dict | None = None,
        after: dict | None = None,
        source: int | None = None,
        target: int | None = None,
        reason: str | None = None,
        system: bool = False,
    ):
        self.repo.add(
            AuditEvent(
                actor_id=actor_id,
                actor_type="SYSTEM" if system else ("USER" if actor_id else "ANONYMOUS"),
                laboratory_id=lab,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                source_revision=source,
                target_revision=target,
                request_id=self.context.request_id,
                correlation_id=self.context.request_id,
                reason=reason,
                before_json={"schema_version": 1, "data": before} if before is not None else None,
                after_json={"schema_version": 1, "data": after} if after is not None else None,
                ip_address=self.context.ip,
                user_agent=self.context.user_agent,
            )
        )
