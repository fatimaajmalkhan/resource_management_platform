"""History: log a change, read a change log."""
from datetime import datetime
from app.models import ResourceHistory

def log_change(session, emp_id, field_name, old_value, new_value, source):
    session.add(ResourceHistory(
        emp_id=emp_id, field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        changed_at=datetime.utcnow(), source=source,
    ))

def get_history(session, emp_id):
    return (session.query(ResourceHistory)
            .filter(ResourceHistory.emp_id == emp_id)
            .order_by(ResourceHistory.changed_at.desc()).all())