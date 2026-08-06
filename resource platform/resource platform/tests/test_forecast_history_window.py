import os
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resource platform")))

import app.server as server


def test_project_workforce_metrics_uses_completed_history_months(monkeypatch):
    monkeypatch.setattr(server, "_history_month_offsets", lambda: [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1])

    def fake_month_bounds(offset):
        label = f"Month {offset}"
        return date(2025, 1, 1), date(2025, 1, 31), label

    monkeypatch.setattr(server, "_month_bounds", fake_month_bounds)

    resources = [
        SimpleNamespace(
            hire_date=date(2024, 1, 1),
            billable_flag=True,
            release_date=None,
            monthly_billing_usd=1000.0,
            daily_rate_usd=100.0,
            job_title="Data Engineer",
            sub_practice="Data Engineering",
            project_client_squad="HQ",
        )
    ]

    projection = server._project_workforce_metrics(resources, months=3, session=None)

    assert [point["month"] for point in projection["history"]] == [
        "Month 12", "Month 11", "Month 10", "Month 9", "Month 8", "Month 7",
        "Month 6", "Month 5", "Month 4", "Month 3", "Month 2", "Month 1"
    ]
    assert projection["history_months_used"] == 12
