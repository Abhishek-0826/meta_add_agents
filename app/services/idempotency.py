"""
Design doc §8: meta_objects is the idempotency backbone. Before creating
anything on Meta, check whether we already have a row for this
(draft_id, object_type). If we do, reuse the stored meta_id instead of
creating a duplicate campaign after a crash/retry.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.meta_object import MetaObject


def get_existing(db: Session, draft_id: UUID, object_type: str) -> MetaObject | None:
    return (
        db.query(MetaObject)
        .filter(MetaObject.draft_id == draft_id, MetaObject.object_type == object_type)
        .one_or_none()
    )


def record_created(db: Session, draft_id: UUID, object_type: str, meta_id: str, status: str = "PAUSED") -> MetaObject:
    obj = MetaObject(
        draft_id=draft_id,
        object_type=object_type,
        meta_id=meta_id,
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_or_create(db: Session, draft_id: UUID, object_type: str, create_fn) -> MetaObject:
    """
    create_fn: zero-arg callable that calls Meta and returns {"id": ..., "status": ...}.
    Only invoked if no idempotent record already exists.
    """
    existing = get_existing(db, draft_id, object_type)
    if existing is not None:
        return existing
    result = create_fn()
    return record_created(db, draft_id, object_type, result["id"], result.get("status", "PAUSED"))
