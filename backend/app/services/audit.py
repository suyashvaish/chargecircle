import json
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.community import AuditLog


def audit(db: Session, user_id: Optional[int], action: str, resource_type: str, resource_id: Any = None,
          details: Optional[Dict[str, Any]] = None, commit: bool = False) -> AuditLog:
    """Writes an audit row. Details are JSON-encoded (never string-formatted) and must not contain secrets."""
    row = AuditLog(user_id=user_id, action=action, resource_type=resource_type,
                   resource_id=str(resource_id) if resource_id is not None else None,
                   details_json=json.dumps(details, default=str) if details else None)
    db.add(row)
    if commit:
        db.commit()
    return row
