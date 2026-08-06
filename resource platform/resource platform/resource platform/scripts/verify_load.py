"""Run this to see what Data Quality actually caught in your data.
   python scripts\\verify_load.py"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import get_session
from app.models import Resource

with get_session() as session:
    total = session.query(Resource).count()
    flagged = session.query(Resource).filter(Resource.data_flag.isnot(None)).all()

    print(f"Total resources loaded: {total}")
    print(f"Flagged by data quality checks: {len(flagged)}\n")

    for r in flagged:
        print(f"  {r.resource_name:<20} -> {r.data_flag}")