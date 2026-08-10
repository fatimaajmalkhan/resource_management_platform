"""Deal and funnel recommendation history — append-only audit log."""
import json
from datetime import datetime
from app.models import DealHistory, FunnelSnapshot


def log_deal_created(session, deal, source):
    session.add(DealHistory(
        deal_id=deal.id,
        deal_name=deal.client_project,
        action="created",
        field_name=None,
        old_value=None,
        new_value=json.dumps({
            "stage": deal.stage,
            "probability": deal.probability,
            "role": deal.role,
            "quantity": deal.quantity,
            "target_month": deal.target_month,
            "practice": deal.practice,
        }),
        changed_at=datetime.utcnow(),
        source=source,
    ))


def log_deal_updated(session, deal, field_name, old_value, new_value, source):
    session.add(DealHistory(
        deal_id=deal.id,
        deal_name=deal.client_project,
        action="updated",
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        changed_at=datetime.utcnow(),
        source=source,
    ))


def log_deal_deleted(session, deal, source):
    session.add(DealHistory(
        deal_id=deal.id,
        deal_name=deal.client_project,
        action="deleted",
        field_name=None,
        old_value=json.dumps({
            "stage": deal.stage,
            "probability": deal.probability,
            "role": deal.role,
            "quantity": deal.quantity,
            "target_month": deal.target_month,
            "practice": deal.practice,
        }),
        new_value=None,
        changed_at=datetime.utcnow(),
        source=source,
    ))


def get_deal_history(session, deal_id=None, limit=50):
    query = session.query(DealHistory).order_by(DealHistory.changed_at.desc())
    if deal_id is not None:
        query = query.filter(DealHistory.deal_id == deal_id)
    return query.limit(limit).all()


def _snapshot_signature(rec):
    return (
        tuple(rec.get("suggested_matches") or []),
        rec.get("shortfall"),
        rec.get("quantity"),
        rec.get("role"),
        rec.get("probability"),
        rec.get("stage"),
    )


def log_funnel_snapshots(session, recommendations, filters):
    """Save recommendation snapshots when they differ from the latest for each deal."""
    filters_json = json.dumps(filters)
    for rec in recommendations:
        last = (
            session.query(FunnelSnapshot)
            .filter(FunnelSnapshot.deal_id == rec["id"])
            .order_by(FunnelSnapshot.computed_at.desc())
            .first()
        )
        if last:
            old_matches = json.loads(last.suggested_matches or "[]")
            old_sig = (tuple(old_matches), last.shortfall, last.quantity, last.role)
            new_sig = (
                tuple(rec.get("suggested_matches") or []),
                rec.get("shortfall"),
                rec.get("quantity"),
                rec.get("role"),
            )
            if old_sig == new_sig:
                continue

        session.add(FunnelSnapshot(
            deal_id=rec["id"],
            client_project=rec["client_project"],
            role=rec["role"],
            quantity=rec["quantity"],
            shortfall=rec["shortfall"],
            suggested_matches=json.dumps(rec.get("suggested_matches") or []),
            recommendation=rec["recommendation"],
            filters_json=filters_json,
            computed_at=datetime.utcnow(),
        ))


def get_funnel_snapshots(session, deal_id=None, limit=50):
    query = session.query(FunnelSnapshot).order_by(FunnelSnapshot.computed_at.desc())
    if deal_id is not None:
        query = query.filter(FunnelSnapshot.deal_id == deal_id)
    return query.limit(limit).all()
