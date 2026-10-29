from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedIdentity:
    tenant_id: str
    object_id: str
    acl_labels: tuple[str, ...]

    @property
    def audit_subject(self):
        return f"{self.tenant_id}:{self.object_id}"
