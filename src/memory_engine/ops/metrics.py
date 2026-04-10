from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_engine.db.models import MetricRollup
from memory_engine.id_utils import new_id, utcnow


def _bucket_bounds():
    now = utcnow()
    bucket_start = now.replace(minute=0, second=0, microsecond=0)
    bucket_end = bucket_start + timedelta(hours=1)
    return bucket_start, bucket_end


def _labels_hash(labels: dict[str, str]) -> str:
    payload = json.dumps(labels, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def increment_metric(session: Session, metric_name: str, *, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
    metric_labels = labels or {}
    bucket_start, bucket_end = _bucket_bounds()
    labels_hash = _labels_hash(metric_labels)
    rollup = session.scalar(
        select(MetricRollup).where(
            MetricRollup.metric_name == metric_name,
            MetricRollup.bucket_start == bucket_start,
            MetricRollup.bucket_end == bucket_end,
            MetricRollup.labels_hash == labels_hash,
        )
    )
    if rollup is None:
        rollup = MetricRollup(
            rollup_id=new_id("metric"),
            metric_name=metric_name,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            labels_hash=labels_hash,
            labels_jsonb=metric_labels,
            value=0.0,
        )
        session.add(rollup)
    rollup.value += value
