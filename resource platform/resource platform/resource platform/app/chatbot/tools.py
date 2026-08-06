"""The chatbot's tool functions -- read-only lookups, plus carefully
   gated write actions that always require explicit confirmation."""

import re
import difflib
from datetime import date, datetime
from sqlalchemy import func, Integer, Float, Boolean, Date, DateTime, Numeric, or_
from app.db import get_session
from app.models import Resource, Deal
from app.history import get_history, log_change
from app.funnel_history import (
    log_deal_created, log_deal_deleted,
    get_deal_history, get_funnel_snapshots,
)
from app.etl import update_resource_in_excel, DB_FIELD_TO_EXCEL_HEADER, normalize_employee_type


# ---------- Serializers -- return every column so the chatbot can see the full record ----------

def _date(v):
    return v.isoformat() if v else None

def serialize_resource(r):
    """Full Resource row -> dict with every field."""
    return {
        "emp_id": r.emp_id,
        "resource_name": r.resource_name,
        "job_title": r.job_title,
        "line_manager": r.line_manager,
        "line_manager_id": r.line_manager_id,
        "practice": r.practice,
        "sub_practice": r.sub_practice,
        "grade": r.grade,
        "employee_type": r.employee_type,
        "project_client_squad": r.project_client_squad,
        "billable_flag": r.billable_flag,
        "billable_pct": r.billable_pct,
        "daily_rate_usd": r.daily_rate_usd,
        "days_billed": r.days_billed,
        "monthly_billing_usd": r.monthly_billing_usd,
        "engagement_start": _date(r.engagement_start),
        "release_date": _date(r.release_date),
        "resource_status": r.resource_status,
        "hire_date": _date(r.hire_date),
        "hrbp": r.hrbp,
        "department": r.department,
        "location_name": r.location_name,
        "email_address": r.email_address,
        "comments": r.comments,
        "data_flag": r.data_flag,
        "loaded_at": r.loaded_at.isoformat() if r.loaded_at else None,
    }

def serialize_deal(d):
    """Full Deal row -> dict with every field."""
    return {
        "id": d.id,
        "client_project": d.client_project,
        "stage": d.stage,
        "probability": d.probability,
        "role": d.role,
        "quantity": d.quantity,
        "target_month": d.target_month,
        "practice": d.practice,
        "notes": d.notes,
    }


def serialize_resource_compact(r):
    """Compact Resource row for list endpoints to prevent exceeding LLM token limit."""
    res = {
        "emp_id": r.emp_id,
        "resource_name": r.resource_name,
        "job_title": r.job_title,
        "line_manager": r.line_manager,
        "practice": r.practice,
        "grade": r.grade,
        "employee_type": r.employee_type,
        "project_client_squad": r.project_client_squad,
        "billable_flag": r.billable_flag,
        "billable_pct": r.billable_pct,
        "daily_rate_usd": r.daily_rate_usd,
        "days_billed": r.days_billed,
        "monthly_billing_usd": r.monthly_billing_usd,
        "engagement_start": _date(r.engagement_start),
        "release_date": _date(r.release_date),
        "hire_date": _date(r.hire_date),
        "resource_status": r.resource_status,
        "location_name": r.location_name,
        "email_address": r.email_address,
    }
    return {k: v for k, v in res.items() if v is not None and v != ""}


# Cap large list results so a single tool call can't blow the LLM context / token budget.
_MAX_ROWS = 25


# ---------- READ-ONLY tools ----------

def get_resource_by_id(emp_id: int):
    """Get the complete record for one resource by their exact employee ID (emp_id)."""
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return {"error": "Employee ID must be an integer"}
    with get_session() as session:
        r = session.query(Resource).filter(Resource.emp_id == emp_id).first()
        if not r:
            return {"error": f"No resource found with employee ID {emp_id}"}
        return serialize_resource(r)


QUERY_RESOURCES_ALLOWED_COLUMNS = {
    "emp_id", "resource_name", "job_title", "line_manager", "line_manager_id",
    "practice", "sub_practice", "grade", "employee_type", "project_client_squad",
    "billable_flag", "billable_pct", "daily_rate_usd", "days_billed", "monthly_billing_usd",
    "engagement_start", "release_date", "resource_status", "hire_date", "hrbp",
    "department", "location_name", "email_address", "comments", "data_flag", "loaded_at"
}


def query_resources(filters: dict = None, group_by: str = None,
                    aggregate: str = None, aggregate_field: str = None):
    """
    filters: e.g. {"grade": "L3", "billable_flag": False,
                   "practice": "Analytics & Insights"}
             -- only equality filters on real Resource columns, validated
                against an explicit allow-list of column names (never
                accept an arbitrary/unvalidated field or raw SQL string).
    group_by: optional column name to group results by (e.g. "practice")
    aggregate: optional one of "count", "sum", "avg"
    aggregate_field: required if aggregate is "sum" or "avg"
                     (e.g. "monthly_billing_usd")

    Returns counts/lists/grouped breakdowns depending on what's passed.
    This must stay parameterized SQLAlchemy query-building -- NEVER
    string-concatenate raw SQL from these inputs.
    """
    ALLOWED_COLUMNS = QUERY_RESOURCES_ALLOWED_COLUMNS

    # Validate filters
    filters_dict = filters or {}
    for col in filters_dict.keys():
        if col not in ALLOWED_COLUMNS:
            return {"error": f"Invalid filter column: '{col}'"}

    # Validate group_by
    if group_by and group_by not in ALLOWED_COLUMNS:
        return {"error": f"Invalid group_by column: '{group_by}'"}

    # Validate aggregate
    if aggregate:
        if aggregate not in {"count", "sum", "avg"}:
            return {"error": f"Invalid aggregate function: '{aggregate}'"}
        if aggregate in {"sum", "avg"} and not aggregate_field:
            return {"error": f"aggregate_field is required for aggregation function '{aggregate}'"}

    # Validate aggregate_field
    if aggregate_field and aggregate_field not in ALLOWED_COLUMNS:
        return {"error": f"Invalid aggregate_field: '{aggregate_field}'"}

    with get_session() as session:
        # Cast filter values according to Resource column types
        processed_filters = []
        for col, val in filters_dict.items():
            # Normalize "active" / "inactive" status values to match DB status "Active" / "Released"
            if col == "resource_status":
                if isinstance(val, str):
                    if val.strip().lower() == "inactive":
                        val = "Released"
                    elif val.strip().lower() == "active":
                        val = "Active"
                elif isinstance(val, list):
                    val = ["Released" if str(v).strip().lower() == "inactive" else "Active" if str(v).strip().lower() == "active" else v for v in val]
                elif isinstance(val, dict):
                    for op_k, op_v in val.items():
                        if isinstance(op_v, str):
                            if op_v.strip().lower() == "inactive":
                                val[op_k] = "Released"
                            elif op_v.strip().lower() == "active":
                                val[op_k] = "Active"

            col_obj = getattr(Resource, col)
            col_type = col_obj.type
            
            if not isinstance(val, (dict, list)) and val is not None:
                if isinstance(col_type, Integer):
                    try:
                        if isinstance(val, str):
                            val = re.sub(r'[$\s,%€£]', '', val)
                        val = int(val)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(col_type, Float) or isinstance(col_type, Numeric):
                    try:
                        if isinstance(val, str):
                            val = re.sub(r'[$\s,%€£]', '', val)
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(col_type, Boolean):
                    if isinstance(val, str):
                        val = val.lower() in ("true", "1", "yes", "t", "y")
                    else:
                        val = bool(val)
                elif isinstance(col_type, Date):
                    if isinstance(val, str):
                        try:
                            val = date.fromisoformat(val)
                        except ValueError:
                            pass
                elif isinstance(col_type, DateTime):
                    if isinstance(val, str):
                        try:
                            val = datetime.fromisoformat(val)
                        except ValueError:
                            pass
            if col_obj.key == "practice" and isinstance(val, str):
                val = val.replace(" and ", " & ").strip()
            processed_filters.append((col_obj, val))

        # Apply filters helper — supports scalar equality, dict range operators, and list IN
        def apply_filters(query_obj):
            for col_obj, val in processed_filters:
                if isinstance(val, dict):
                    for op_key, op_val in val.items():
                        if op_key == "gt":
                            query_obj = query_obj.filter(col_obj > op_val)
                        elif op_key == "gte":
                            query_obj = query_obj.filter(col_obj >= op_val)
                        elif op_key == "lt":
                            query_obj = query_obj.filter(col_obj < op_val)
                        elif op_key == "lte":
                            query_obj = query_obj.filter(col_obj <= op_val)
                        elif op_key == "ne":
                            query_obj = query_obj.filter(col_obj != op_val)
                elif isinstance(val, list):
                    if all(isinstance(v, str) for v in val):
                        query_obj = query_obj.filter(func.lower(col_obj).in_([v.strip().lower() for v in val]))
                    else:
                        query_obj = query_obj.filter(col_obj.in_(val))
                elif isinstance(val, str):
                    query_obj = query_obj.filter(func.lower(col_obj) == val.strip().lower())
                else:
                    query_obj = query_obj.filter(col_obj == val)
            return query_obj

        # 1. Group by + Aggregate
        if group_by and aggregate:
            group_col = getattr(Resource, group_by)
            if aggregate == "count":
                agg_func = func.count(Resource.emp_id)
            elif aggregate == "sum":
                agg_func = func.sum(getattr(Resource, aggregate_field))
            elif aggregate == "avg":
                agg_func = func.avg(getattr(Resource, aggregate_field))

            q = session.query(group_col, agg_func)
            q = apply_filters(q)
            q = q.group_by(group_col)
            results = q.all()

            if not results:
                return {"error": "No records found matching the query criteria."}

            breakdown = []
            for g_val, a_val in results:
                if isinstance(a_val, float):
                    a_val = round(a_val, 2)
                breakdown.append({
                    group_by: g_val if g_val is not None else "Unspecified",
                    aggregate: a_val
                })
            return {"breakdown": breakdown}

        # 2. Group by only (List of lists grouped by group_by column)
        elif group_by and not aggregate:
            q = session.query(Resource)
            q = apply_filters(q)
            rows = q.all()

            if not rows:
                return {"error": "No records found matching the query criteria."}

            grouped = {}
            for r in rows:
                key = getattr(r, group_by)
                key_str = str(key) if key is not None else "Unspecified"
                grouped.setdefault(key_str, []).append(serialize_resource_compact(r))

            # Cap each group to _MAX_ROWS to prevent blowing context window
            capped_grouped = {}
            for k, v in grouped.items():
                capped_grouped[k] = v[:_MAX_ROWS]

            return {
                "grouped": capped_grouped,
                "total_count": len(rows),
                "returned_groups": len(capped_grouped)
            }

        # 3. Aggregate only
        elif aggregate and not group_by:
            if aggregate == "count":
                agg_func = func.count(Resource.emp_id)
            elif aggregate == "sum":
                agg_func = func.sum(getattr(Resource, aggregate_field))
            elif aggregate == "avg":
                agg_func = func.avg(getattr(Resource, aggregate_field))

            q = session.query(agg_func)
            q = apply_filters(q)
            a_val = q.scalar()

            if a_val is None or (aggregate == "count" and a_val == 0):
                return {"error": "No records found matching the query criteria."}

            if isinstance(a_val, float):
                a_val = round(a_val, 2)
            return {aggregate: a_val}

        # 4. Neither group_by nor aggregate (Simple query of rows)
        else:
            q = session.query(Resource)
            q = apply_filters(q)
            rows = q.all()

            if not rows:
                return {"error": "No records found matching the query criteria."}

            limited = [serialize_resource_compact(r) for r in rows[:_MAX_ROWS]]
            result = {"total_count": len(rows), "returned": len(limited), "resources": limited}
            if len(rows) > _MAX_ROWS:
                result["note"] = f"Showing first {_MAX_ROWS} of {len(rows)}. Add more filters to narrow the search."
            return result


def get_resources_by_practice(practice: str):
    # Normalize "and" to "&" and strip spaces for user-friendliness
    practice_norm = practice.replace(" and ", " & ").strip()
    with get_session() as session:
        # Query case-insensitively using ilike with wildcards for partial matches
        rows = session.query(Resource).filter(Resource.practice.ilike(f"%{practice_norm}%")).all()
        if not rows:
            return {"error": f"No resources found in practice '{practice}'"}
        total_count = len(rows)
        limited = [serialize_resource_compact(r) for r in rows[:_MAX_ROWS]]
        result = {"total_count": total_count, "returned": len(limited), "resources": limited}
        if total_count > _MAX_ROWS:
            result["note"] = f"Showing first {_MAX_ROWS} of {total_count}. Narrow your query to see the rest."
        return result


def get_overview_summary():
    """Return current workforce overview metrics including revenue and billing totals."""
    from app.server import get_benched_resources

    with get_session() as session:
        resources = session.query(Resource).all()
        billable_count = sum(1 for r in resources if r.billable_flag)
        benched = get_benched_resources(session)
        total_monthly_billing = sum(
            r.monthly_billing_usd if r.monthly_billing_usd is not None else ((r.daily_rate_usd or 0) * 20)
            if r.billable_flag else 0
            for r in resources
        )
        rates = [r.daily_rate_usd for r in resources if r.daily_rate_usd]
        avg_daily_rate = round(sum(rates) / len(rates)) if rates else 0
        headcount = len(resources)
        bench_rate = round(len(benched) / headcount * 100, 1) if headcount else 0

        return {
            "headcount": headcount,
            "billable_count": billable_count,
            "benched_count": len(benched),
            "bench_rate": bench_rate,
            "total_monthly_billing": round(total_monthly_billing, 2),
            "avg_daily_rate": avg_daily_rate,
            "note": "Current totals are based on active resources and monthly billing values; billable status is determined by billable_flag."
        }


def get_forecast_summary(months: int = 3, win_probability_floor: float = 50.0, attrition_rate: float = 0.0,
                         trend_scalar: float = 1.0, daily_rate_scaler: float = 1.0, model_type: str = "hybrid"):
    """Return forecasted headcount, billable count, benched, and revenue that match the platform's prediction graph."""
    from app.server import _project_workforce_metrics

    with get_session() as session:
        resources = session.query(Resource).all()
        projection = _project_workforce_metrics(
            resources,
            months,
            win_probability_floor=win_probability_floor,
            attrition_rate=attrition_rate,
            trend_scalar=trend_scalar,
            daily_rate_scaler=daily_rate_scaler,
            model_type=model_type,
            session=session,
        )
        return {
            "history": projection["history"],
            "forecast": projection["forecast"],
            "model_type": model_type,
            "confidence_level": 0.80,
            "note": "Forecast uses the last 12 completed months and matches the platform's prediction engine for revenue, billable, headcount, and bench metrics."
        }


def _resolve_resource_name(session, resource_name: str):
    """
    Resolve a name to a single Resource row, with disambiguation.
    Returns (Resource, None) on success, or (None, error_dict) on failure/ambiguity.
    """
    # 1. Exact case-insensitive match
    exact = session.query(Resource).filter(
        func.lower(Resource.resource_name) == resource_name.strip().lower()
    ).all()
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, {
            "ambiguous": True,
            "message": f"Multiple resources match '{resource_name}'. Please specify which one:",
            "matches": [{"emp_id": r.emp_id, "resource_name": r.resource_name, "job_title": r.job_title, "practice": r.practice} for r in exact]
        }

    # 2. Substring match (ilike)
    substr = session.query(Resource).filter(Resource.resource_name.ilike(f"%{resource_name}%")).all()
    if len(substr) == 1:
        return substr[0], None
    if len(substr) > 1:
        return None, {
            "ambiguous": True,
            "message": f"Multiple resources match '{resource_name}'. Please specify which one:",
            "matches": [{"emp_id": r.emp_id, "resource_name": r.resource_name, "job_title": r.job_title, "practice": r.practice} for r in substr[:10]]
        }

    # 3. Fuzzy match
    all_names = [res.resource_name for res in session.query(Resource.resource_name).all()]
    fuzzy = difflib.get_close_matches(resource_name, all_names, n=3, cutoff=0.7)
    if len(fuzzy) == 1:
        r = session.query(Resource).filter(Resource.resource_name == fuzzy[0]).first()
        return r, None
    if len(fuzzy) > 1:
        return None, {
            "ambiguous": True,
            "message": f"No exact match for '{resource_name}'. Did you mean one of these?",
            "matches": [{"resource_name": n} for n in fuzzy]
        }

    return None, {"error": f"No resource found matching '{resource_name}'"}


def get_resource_summary(resource_name: str):
    with get_session() as session:
        r, err = _resolve_resource_name(session, resource_name)
        if err:
            return err
        return serialize_resource(r)


def _is_blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _matches_missing_job_title_query(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).strip().lower()
    if not text:
        return False
    if "job" in text or "title" in text:
        negative_terms = ["without", "no", "none", "missing", "blank", "empty", "not having", "not provided", "not set", "lacking", "absent", "null"]
        return any(term in text for term in negative_terms)
    return False


def search_resources(query: str = None, practice: str = None, status: str = None,
                     job_title: str = None, department: str = None, billable: bool = None,
                     grade: str = None, employee_type: str = None, location: str = None,
                     daily_rate_usd: float = None, min_daily_rate: float = None, max_daily_rate: float = None,
                     billable_pct: float = None, min_billable_pct: float = None, max_billable_pct: float = None,
                     days_billed: float = None, min_days_billed: float = None, max_days_billed: float = None,
                     monthly_billing_usd: float = None, min_monthly_billing: float = None, max_monthly_billing: float = None,
                     hrbp: str = None, sub_practice: str = None, line_manager: str = None,
                     project_client_squad: str = None,
                     min_hire_date: str = None, max_hire_date: str = None,
                     min_engagement_start: str = None, max_engagement_start: str = None,
                     min_release_date: str = None, max_release_date: str = None,
                     sort_by: str = None, sort_order: str = "asc", limit: int = None):
    """Flexible resource search across any combination of fields. Returns full records."""
    with get_session() as session:
        q = session.query(Resource)
        if query:
            clean_query = query.strip().lower()
            is_missing_job_title_request = _matches_missing_job_title_query(clean_query)
            if clean_query not in ["all", "everyone", "any", "people", "person", "resource", "resources", "employee", "employees", "staff", "who"]:
                if is_missing_job_title_request:
                    q = q.filter(or_(Resource.job_title.is_(None), func.trim(Resource.job_title) == ""))
                else:
                    like = f"%{query}%"
                    q = q.filter(
                        Resource.resource_name.ilike(like)
                        | Resource.email_address.ilike(like)
                        | Resource.job_title.ilike(like)
                        | Resource.project_client_squad.ilike(like)
                        | Resource.grade.ilike(like)
                        | Resource.employee_type.ilike(like)
                        | Resource.location_name.ilike(like)
                        | Resource.practice.ilike(like)
                        | Resource.sub_practice.ilike(like)
                        | Resource.department.ilike(like)
                        | Resource.line_manager.ilike(like)
                        | Resource.hrbp.ilike(like)
                    )
        if practice:
            q = q.filter(Resource.practice.ilike(f"%{practice.replace(' and ', ' & ').strip()}%"))
        if status:
            status_clean = status.strip().lower()
            if "inactive" in status_clean or "released" in status_clean:
                q = q.filter(Resource.resource_status.ilike("%Released%"))
            elif "active" in status_clean:
                q = q.filter(Resource.resource_status.ilike("%Active%"))
            else:
                q = q.filter(Resource.resource_status.ilike(f"%{status}%"))
        if job_title is not None:
            if _is_blank(job_title) or _matches_missing_job_title_query(job_title):
                q = q.filter(or_(Resource.job_title.is_(None), func.trim(Resource.job_title) == ""))
            else:
                q = q.filter(Resource.job_title.ilike(f"%{job_title}%"))
        if department:
            q = q.filter(Resource.department.ilike(f"%{department}%"))
        if grade:
            q = q.filter(Resource.grade.ilike(f"%{grade}%"))
        if employee_type:
            q = q.filter(Resource.employee_type.ilike(f"%{normalize_employee_type(employee_type)}%"))
        if location:
            q = q.filter(Resource.location_name.ilike(f"%{location}%"))
        if billable is not None:
            if billable:
                q = q.filter(Resource.billable_flag.is_(True))
            else:
                q = q.filter((Resource.billable_flag.is_(False)) | (Resource.billable_flag.is_(None)))

        # Numerical filters
        def safe_float(v):
            if v is None:
                return None
            try:
                if isinstance(v, str):
                    v = re.sub(r'[$\s,%€£]', '', v)
                return float(v)
            except (ValueError, TypeError):
                return None

        daily_rate_usd_val = safe_float(daily_rate_usd)
        min_daily_rate_val = safe_float(min_daily_rate)
        max_daily_rate_val = safe_float(max_daily_rate)

        billable_pct_val = safe_float(billable_pct)
        min_billable_pct_val = safe_float(min_billable_pct)
        max_billable_pct_val = safe_float(max_billable_pct)

        days_billed_val = safe_float(days_billed)
        min_days_billed_val = safe_float(min_days_billed)
        max_days_billed_val = safe_float(max_days_billed)

        monthly_billing_usd_val = safe_float(monthly_billing_usd)
        min_monthly_billing_val = safe_float(min_monthly_billing)
        max_monthly_billing_val = safe_float(max_monthly_billing)

        if daily_rate_usd_val is not None:
            q = q.filter(Resource.daily_rate_usd == daily_rate_usd_val)
        if min_daily_rate_val is not None:
            q = q.filter(Resource.daily_rate_usd >= min_daily_rate_val)
        if max_daily_rate_val is not None:
            q = q.filter(Resource.daily_rate_usd <= max_daily_rate_val)

        if billable_pct_val is not None:
            q = q.filter(Resource.billable_pct == billable_pct_val)
        if min_billable_pct_val is not None:
            q = q.filter(Resource.billable_pct >= min_billable_pct_val)
        if max_billable_pct_val is not None:
            q = q.filter(Resource.billable_pct <= max_billable_pct_val)

        if days_billed_val is not None:
            q = q.filter(Resource.days_billed == days_billed_val)
        if min_days_billed_val is not None:
            q = q.filter(Resource.days_billed >= min_days_billed_val)
        if max_days_billed_val is not None:
            q = q.filter(Resource.days_billed <= max_days_billed_val)

        if monthly_billing_usd_val is not None:
            q = q.filter(Resource.monthly_billing_usd == monthly_billing_usd_val)
        if min_monthly_billing_val is not None:
            q = q.filter(Resource.monthly_billing_usd >= min_monthly_billing_val)
        if max_monthly_billing_val is not None:
            q = q.filter(Resource.monthly_billing_usd <= max_monthly_billing_val)

        def safe_date(v):
            if not v:
                return None
            try:
                return date.fromisoformat(str(v).strip())
            except ValueError:
                return None

        if hrbp:
            q = q.filter(Resource.hrbp.ilike(f"%{hrbp}%"))
        if sub_practice:
            q = q.filter(Resource.sub_practice.ilike(f"%{sub_practice}%"))
        if line_manager:
            q = q.filter(Resource.line_manager.ilike(f"%{line_manager}%"))
        if project_client_squad:
            q = q.filter(Resource.project_client_squad.ilike(f"%{project_client_squad}%"))

        if d := safe_date(min_hire_date):
            q = q.filter(Resource.hire_date >= d)
        if d := safe_date(max_hire_date):
            q = q.filter(Resource.hire_date <= d)
        if d := safe_date(min_engagement_start):
            q = q.filter(Resource.engagement_start >= d)
        if d := safe_date(max_engagement_start):
            q = q.filter(Resource.engagement_start <= d)
        if d := safe_date(min_release_date):
            q = q.filter(Resource.release_date >= d)
        if d := safe_date(max_release_date):
            q = q.filter(Resource.release_date <= d)

        if sort_by:
            try:
                sort_col = getattr(Resource, sort_by)
            except AttributeError:
                return {"error": f"Invalid sort_by column: '{sort_by}'"}
            q = q.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        rows = q.all()
        if not rows:
            return {"error": "No resources found matching the search criteria."}
        total_count = len(rows)
        effective_limit = min(limit, 100) if limit else _MAX_ROWS
        limited = [serialize_resource_compact(r) for r in rows[:effective_limit]]
        result = {"total_count": total_count, "returned": len(limited), "resources": limited}
        if total_count > effective_limit:
            result["note"] = f"Showing first {effective_limit} of {total_count}. Add more filters to narrow the search."
        return result


def list_deals(month: str = None, role: str = None, practice: str = None, stage: str = None):
    """List sales pipeline deals (full records), optionally filtered."""
    with get_session() as session:
        q = session.query(Deal)
        if month:
            q = q.filter(Deal.target_month == month)
        if role:
            q = q.filter(Deal.role.ilike(f"%{role}%"))
        if practice:
            q = q.filter(Deal.practice.ilike(f"%{practice.replace(' and ', ' & ').strip()}%"))
        if stage:
            q = q.filter(Deal.stage.ilike(f"%{stage}%"))
        rows = q.all()
        if not rows:
            return {"error": "No deals found matching the search criteria."}
        return {"total_count": len(rows), "deals": [serialize_deal(d) for d in rows[:_MAX_ROWS]]}


def get_flagged_resources():
    with get_session() as session:
        rows = session.query(Resource).filter(Resource.data_flag.isnot(None)).all()
        if not rows:
            return {"error": "No flagged resources found."}
        return [{"name": r.resource_name, "emp_id": r.emp_id, "flag": r.data_flag} for r in rows]


def get_resource_history(resource_name: str):
    with get_session() as session:
        r, err = _resolve_resource_name(session, resource_name)
        if err:
            return err
        history = get_history(session, r.emp_id)
        if not history:
            return {"error": f"No history found for resource '{r.resource_name}' (ID: {r.emp_id})"}
        return [{"field": h.field_name, "old": h.old_value, "new": h.new_value,
                  "when": h.changed_at.isoformat(), "source": h.source} for h in history]


# ---------- WRITE tools -- always propose first, apply only after confirmation ----------

ALLOWED_FIELDS = {
    "grade", "resource_status", "project_client_squad",
    "line_manager", "daily_rate_usd", "billable_flag",
    "practice", "job_title", "sub_practice",
    "employee_type", "billable_pct", "hrbp", "comments",
}

def propose_change(resource_name: str, field: str, new_value: str):
    if field not in ALLOWED_FIELDS:
        return {"error": f"'{field}' can't be changed via chat commands yet."}
    with get_session() as session:
        r, err = _resolve_resource_name(session, resource_name)
        if err:
            return err
        return {"emp_id": r.emp_id, "resource_name": r.resource_name, "field": field,
                "old_value": getattr(r, field), "new_value": new_value, "confirmation_required": True}


def apply_change(emp_id: int, field: str, new_value: str, confirmed_by: str):
    with get_session() as session:
        r = session.get(Resource, emp_id)
        if not r:
            return {"error": "Resource no longer exists"}
        if field not in ALLOWED_FIELDS:
            return {"error": f"Field '{field}' is not editable via chat."}
        col_type = getattr(Resource, field).type
        typed_value = new_value
        if isinstance(col_type, Boolean):
            typed_value = str(new_value).lower() in ("true", "yes", "1", "y")
        elif isinstance(col_type, (Float, Numeric)):
            try:
                typed_value = float(re.sub(r'[$\s,%]', '', str(new_value)))
            except ValueError:
                return {"error": f"Invalid numeric value '{new_value}' for field '{field}'"}
        elif field == "employee_type":
            typed_value = normalize_employee_type(new_value)
        old_value = getattr(r, field)
        setattr(r, field, typed_value)
        log_change(session, emp_id, field, old_value, typed_value, source=f"chatbot_command:{confirmed_by}")
        session.commit()

        excel_synced = True
        try:
            record = {"emp_id": r.emp_id, **{f: getattr(r, f) for f in DB_FIELD_TO_EXCEL_HEADER}}
            update_resource_in_excel(record)
        except Exception as e:
            print(f"Excel update failed for emp_id {emp_id}: {e}")
            excel_synced = False

        return {"status": "applied", "resource_name": r.resource_name,
                "field": field, "old_value": old_value, "new_value": typed_value,
                "excel_synced": excel_synced}


# ---------- Sales Pipeline & Hiring Funnel chatbot tools ----------

def get_funnel_summary(month: str = None, role: str = None, practice: str = None):
    from app.server import get_benched_resources, match_role
    with get_session() as session:
        query = session.query(Deal)
        if month:
            query = query.filter(Deal.target_month == month)
        if role:
            query = query.filter(Deal.role.ilike(f"%{role}%"))
        if practice:
            practice_norm = practice.replace(" and ", " & ").strip()
            query = query.filter(Deal.practice.ilike(f"%{practice_norm}%"))
            
        deals = query.all()
        if not deals:
            return {"error": "No deals found matching the criteria."}
            
        benched = get_benched_resources(session)
        
        cautious_estimate = 0.0
        hopeful_estimate = 0.0
        
        summary_lines = []
        summary_lines.append("### Sales Pipeline & Hiring Funnel Summary")
        if month or role or practice:
            filters = []
            if month: filters.append(f"Month: {month}")
            if role: filters.append(f"Role: {role}")
            if practice: filters.append(f"Practice: {practice}")
            summary_lines.append(f"*Filters applied: {', '.join(filters)}*")
        summary_lines.append("")
        
        deal_lines = []
        for d in deals:
            expected_demand = d.quantity * (d.probability / 100.0)
            hopeful_estimate += expected_demand
            if d.probability >= 70.0:
                cautious_estimate += expected_demand
                
            matching_benched = []
            for r in benched:
                if match_role(r, d.role):
                    matching_benched.append(r)
            matching_benched.sort(key=lambda r: 0 if (r.practice or "").lower() == (d.practice or "").lower() else 1)
            
            suggested = matching_benched[:d.quantity]
            suggested_names = [s.resource_name for s in suggested]
            shortfall = max(0, d.quantity - len(suggested))
            
            deal_desc = f"- **{d.client_project}** ({d.stage}, Win Prob: {d.probability}%, Month: {d.target_month})"
            deal_desc += f"\n  - Role: {d.role} | Needed: {d.quantity} (Expected Demand: {expected_demand:.1f})"
            if suggested_names:
                deal_desc += f"\n  - Suggested Matches: {', '.join(suggested_names)}"
            else:
                deal_desc += f"\n  - Suggested Matches: None"
            if shortfall > 0:
                deal_desc += f"\n  - ⚠️ Shortfall: {shortfall} | Recommendation: **Hire {shortfall} {d.role}(s)**"
            else:
                deal_desc += f"\n  - ✅ Recommendation: Fully staffed from bench"
            deal_lines.append(deal_desc)
            
        summary_lines.append("**Forecasted Resource Demand:**")
        summary_lines.append(f"- **Cautious Estimate** (deals >= 70% probability): **{cautious_estimate:.2f}** expected resources")
        summary_lines.append(f"- **Hopeful Estimate** (all active deals): **{hopeful_estimate:.2f}** expected resources")
        summary_lines.append("")
        summary_lines.append("**Active Deals & Recommendations:**")
        summary_lines.extend(deal_lines)
        
        return "\n".join(summary_lines)


def add_deal(client_project: str, stage: str, probability: float, role: str, quantity: int, target_month: str, practice: str, notes: str = None):
    with get_session() as session:
        db_deal = Deal(
            client_project=client_project,
            stage=stage,
            probability=probability,
            role=role,
            quantity=quantity,
            target_month=target_month,
            practice=practice,
            notes=notes
        )
        session.add(db_deal)
        session.commit()
        session.refresh(db_deal)
        log_deal_created(session, db_deal, source="chatbot")
        session.commit()
        return f"Successfully added deal **{client_project}** (ID: {db_deal.id}) requesting {quantity} {role}(s) for {target_month} under practice '{practice}'."


def delete_deal(deal_id: int):
    with get_session() as session:
        db_deal = session.get(Deal, deal_id)
        if not db_deal:
            return {"error": f"No deal found with ID {deal_id}."}
        name = db_deal.client_project
        log_deal_deleted(session, db_deal, source="chatbot")
        session.delete(db_deal)
        session.commit()
        return f"Successfully deleted deal **{name}** (ID: {deal_id})."


def get_funnel_history(deal_id: int = None, limit: int = 20):
    import json as _json
    with get_session() as session:
        deal_rows = get_deal_history(session, deal_id=deal_id, limit=limit)
        snap_rows = get_funnel_snapshots(session, deal_id=deal_id, limit=limit)
        if not deal_rows and not snap_rows:
            return {"error": "No funnel history or snapshots found."}

        lines = ["### Funnel History"]
        if deal_id:
            lines.append(f"*Filtered to deal ID {deal_id}*")
        lines.append("")

        lines.append("**Deal Changes:**")
        if not deal_rows:
            lines.append("- No deal change history recorded yet.")
        else:
            for h in deal_rows:
                when = h.changed_at.strftime("%Y-%m-%d %H:%M UTC")
                if h.action == "created":
                    lines.append(f"- [{when}] **Created** deal #{h.deal_id} *{h.deal_name}* (via {h.source})")
                elif h.action == "deleted":
                    lines.append(f"- [{when}] **Deleted** deal #{h.deal_id} *{h.deal_name}* (via {h.source})")
                else:
                    lines.append(f"- [{when}] **Updated** *{h.deal_name}*: `{h.field_name}` {h.old_value} → {h.new_value} (via {h.source})")

        lines.append("")
        lines.append("**Recommendation Snapshots:**")
        if not snap_rows:
            lines.append("- No recommendation snapshots recorded yet. Snapshots are saved when recommendations change.")
        else:
            for s in snap_rows:
                when = s.computed_at.strftime("%Y-%m-%d %H:%M UTC")
                matches = _json.loads(s.suggested_matches or "[]")
                match_str = ", ".join(matches) if matches else "None"
                lines.append(f"- [{when}] *{s.client_project}* — {s.role} x{s.quantity}, shortfall: {s.shortfall}, matches: {match_str}")

        return "\n".join(lines)


def calculate_duration(start_date: str, end_date: str = None):
    """
    Calculate the duration/difference between two dates in days, weeks, months, and years.
    If end_date is not provided, today's date is used.
    Use this to calculate tenure or how many months an employee worked or was hired.
    """
    try:
        start = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        return {"error": f"Invalid start_date format: '{start_date}'. Must be YYYY-MM-DD."}
        
    if end_date:
        try:
            end = date.fromisoformat(end_date)
        except (ValueError, TypeError):
            return {"error": f"Invalid end_date format: '{end_date}'. Must be YYYY-MM-DD."}
    else:
        end = date.today()
        
    delta_days = (end - start).days
    delta_weeks = round(delta_days / 7.0, 1)
    delta_months = round(delta_days / 30.4375, 1)
    delta_years = round(delta_days / 365.25, 1)
    
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": delta_days,
        "weeks": delta_weeks,
        "months": delta_months,
        "years": delta_years
    }


# ---------- Tool schemas + function map, for wiring into the Claude API ----------

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_resource_by_id",
        "description": "Get the complete record for one resource by their exact employee ID (emp_id).",
        "parameters": {"type": "object", "properties": {"emp_id": {"type": "integer"}}, "required": ["emp_id"]}}},
    {"type": "function", "function": {
        "name": "query_resources",
        "description": "Generic query tool to filter, count, and aggregate across resource fields. Supports equality, range, and IN-list filters.",
        "parameters": {"type": "object", "properties": {
            "filters": {"type": "object", "description": (
                "Filters as key-value pairs; allowed keys are the same resource columns as group_by's enum. "
                "Values: a scalar (equality, e.g. 'L3', true/false), a range dict "
                "({'gte'/'gt'/'lte'/'lt'/'ne': X}), or a list for IN (e.g. ['L1', 'L2']). "
                "Examples: {'grade': 'L3'}, {'billable_flag': false}, {'daily_rate_usd': {'gte': 150}}"
            )},
            "group_by": {"type": "string", "description": "Optional column name to group results by (e.g. 'practice', 'grade', 'location_name')",
                         "enum": sorted(QUERY_RESOURCES_ALLOWED_COLUMNS)},
            "aggregate": {"type": "string", "description": "Optional aggregation function", "enum": ["count", "sum", "avg"]},
            "aggregate_field": {"type": "string", "description": "Optional column to aggregate on (required if aggregate is 'sum' or 'avg', e.g. 'monthly_billing_usd')",
                                "enum": sorted(QUERY_RESOURCES_ALLOWED_COLUMNS)}
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "get_resources_by_practice",
        "description": "List all resources in a given practice (e.g. 'Analytics & Insights'), returning every field for each resource (billing, rates, dates, manager, location, etc.).",
        "parameters": {"type": "object", "properties": {"practice": {"type": "string"}}, "required": ["practice"]}}},
    {"type": "function", "function": {
        "name": "get_resource_summary",
        "description": "Get the complete record for one named resource: every field including email, job title, manager, grade, practice, sub-practice, project, status, billing flag/percent, daily rate, days billed, monthly billing, hire/engagement/release dates, HRBP, department, location, comments, and data flags.",
        "parameters": {"type": "object", "properties": {"resource_name": {"type": "string"}}, "required": ["resource_name"]}}},
    {"type": "function", "function": {
        "name": "get_overview_summary",
        "description": "Get current workforce overview metrics including headcount, billable count, benched count, bench rate, total monthly billing, and average daily rate.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_forecast_summary",
        "description": "Get forecasted headcount, billable, benched, and revenue values for the next 1-3 months that match the platform's prediction graph.",
        "parameters": {"type": "object", "properties": {
            "months": {"type": "integer", "description": "Number of months to forecast (1-3)."},
            "win_probability_floor": {"type": "number", "description": "Minimum deal probability to include in pipeline-driven staffing."},
            "attrition_rate": {"type": "number", "description": "Monthly attrition rate percentage."},
            "trend_scalar": {"type": "number", "description": "Trend multiplier for the forecast."},
            "daily_rate_scaler": {"type": "number", "description": "Multiplier to scale revenue from role daily rates."},
            "model_type": {"type": "string", "description": "Forecast model type: 'hybrid' or 'ols'."}
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "search_resources",
        "description": "Flexible search across ALL resources by any combination of a free-text query, practice, status, job_title, department, billable flag, grade, location, employee_type, or numerical attributes (daily rate, billable %, days billed, monthly billing). Returns full records.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Free text matched against name, email, job title, project, grade, employee_type, location, manager, etc."},
            "practice": {"type": "string"}, "status": {"type": "string"},
            "job_title": {"type": "string"}, "department": {"type": "string"},
            "billable": {"type": "boolean"},
            "location": {"type": "string", "description": "Resource location (e.g. Karachi, Lahore, Dubai, etc.)"},
            "grade": {"type": "string", "description": "Resource grade (e.g. L1, L2, L3, L4, L5, Contractual)"},
            "employee_type": {"type": "string", "description": "Employee type (e.g. Full-Time Regular, Contractual, Probationary)"},
            "daily_rate_usd": {"type": "number", "description": "Exact daily rate (USD)"},
            "min_daily_rate": {"type": "number"}, "max_daily_rate": {"type": "number"},
            "billable_pct": {"type": "number"},
            "min_billable_pct": {"type": "number"}, "max_billable_pct": {"type": "number"},
            "days_billed": {"type": "number"},
            "min_days_billed": {"type": "number"}, "max_days_billed": {"type": "number"},
            "monthly_billing_usd": {"type": "number", "description": "Exact monthly billing (USD)"},
            "min_monthly_billing": {"type": "number"}, "max_monthly_billing": {"type": "number"},
            "hrbp": {"type": "string", "description": "HRBP name (partial match)"},
            "sub_practice": {"type": "string"},
            "line_manager": {"type": "string", "description": "Line manager name (partial match) -- use for 'who reports to X'"},
            "project_client_squad": {"type": "string", "description": "Project/client/squad name (partial match)"},
            "min_hire_date": {"type": "string", "description": "Earliest hire date, inclusive (YYYY-MM-DD)"},
            "max_hire_date": {"type": "string", "description": "Latest hire date, inclusive (YYYY-MM-DD)"},
            "min_engagement_start": {"type": "string", "description": "Earliest engagement start, inclusive (YYYY-MM-DD)"},
            "max_engagement_start": {"type": "string", "description": "Latest engagement start, inclusive (YYYY-MM-DD)"},
            "min_release_date": {"type": "string", "description": "Earliest release date, inclusive (YYYY-MM-DD)"},
            "max_release_date": {"type": "string", "description": "Latest release date, inclusive (YYYY-MM-DD)"},
            "sort_by": {"type": "string", "description": "Column to sort by (e.g. 'daily_rate_usd', 'hire_date')"},
            "sort_order": {"type": "string", "description": "'asc' or 'desc' (default 'asc'); use 'desc' for highest/most-recent-first"},
            "limit": {"type": "integer", "description": "Max rows (default 25, max 100); combine with sort_by for Top-N"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "list_deals",
        "description": "List sales pipeline deals with full details (client/project, stage, probability, role, quantity, target month, practice, notes). Optionally filter by month, role, practice, or stage.",
        "parameters": {"type": "object", "properties": {
            "month": {"type": "string"}, "role": {"type": "string"},
            "practice": {"type": "string"}, "stage": {"type": "string"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "get_flagged_resources",
        "description": "List every resource currently flagged by data quality checks.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_resource_history",
        "description": "Get the full change history for one named resource.",
        "parameters": {"type": "object", "properties": {"resource_name": {"type": "string"}}, "required": ["resource_name"]}}},
    {"type": "function", "function": {
        "name": "propose_change",
        "description": "Propose changing a field for a resource. Does NOT apply it — returns the old/new value for user confirmation. Editable fields: grade, resource_status, project_client_squad, line_manager, daily_rate_usd, billable_flag, practice, job_title, sub_practice, employee_type, billable_pct, hrbp, comments.",
        "parameters": {"type": "object", "properties": {
            "resource_name": {"type": "string"}, "field": {"type": "string"}, "new_value": {"type": "string"}},
            "required": ["resource_name", "field", "new_value"]}}},
    {"type": "function", "function": {
        "name": "apply_change",
        "description": "Apply a previously proposed change. Only call this after the user has explicitly confirmed.",
        "parameters": {"type": "object", "properties": {
            "emp_id": {"type": "integer"}, "field": {"type": "string"},
            "new_value": {"type": "string"}, "confirmed_by": {"type": "string"}},
            "required": ["emp_id", "field", "new_value", "confirmed_by"]}}},
    {"type": "function", "function": {
        "name": "get_funnel_summary",
        "description": "Get a summary of sales pipeline deals, expected resource demand (cautious/hopeful estimates), suggested benched matches, and shortfall recommendations.",
        "parameters": {"type": "object", "properties": {
            "month": {"type": "string", "description": "Optional target month (format YYYY-MM)"},
            "role": {"type": "string", "description": "Optional role type (Data Engineer, BI, DBA, Other)"},
            "practice": {"type": "string", "description": "Optional practice name (e.g. Analytics & Insights)"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "add_deal",
        "description": "Add a new sales pipeline deal to the funnel.",
        "parameters": {"type": "object", "properties": {
            "client_project": {"type": "string"}, "stage": {"type": "string"},
            "probability": {"type": "number"}, "role": {"type": "string"},
            "quantity": {"type": "integer"}, "target_month": {"type": "string"},
            "practice": {"type": "string"}, "notes": {"type": "string"}},
            "required": ["client_project", "stage", "probability", "role", "quantity", "target_month", "practice"]}}},
    {"type": "function", "function": {
        "name": "delete_deal",
        "description": "Delete a sales pipeline deal from the funnel.",
        "parameters": {"type": "object", "properties": {
            "deal_id": {"type": "integer"}},
            "required": ["deal_id"]}}},
    {"type": "function", "function": {
        "name": "get_funnel_history",
        "description": "Get deal change history and funnel recommendation snapshots. Optionally filter by deal_id.",
        "parameters": {"type": "object", "properties": {
            "deal_id": {"type": "integer", "description": "Optional deal ID to filter history"},
            "limit": {"type": "integer", "description": "Max records to return (default 20)"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "calculate_duration",
        "description": "Calculate the duration/difference between two dates (YYYY-MM-DD format). If end_date is not provided, today's date is used. Use this to calculate how many months ago someone was hired, how long they have worked, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "The start date in YYYY-MM-DD format"},
                "end_date": {"type": "string", "description": "Optional end date in YYYY-MM-DD format. Defaults to today's date."}
            },
            "required": ["start_date"]
        }}},
]

FUNCTION_MAP = {
    "get_resource_by_id": get_resource_by_id,
    "query_resources": query_resources,
    "get_resources_by_practice": get_resources_by_practice,
    "get_resource_summary": get_resource_summary,
    "get_overview_summary": get_overview_summary,
    "get_forecast_summary": get_forecast_summary,
    "search_resources": search_resources,
    "list_deals": list_deals,
    "get_flagged_resources": get_flagged_resources,
    "get_resource_history": get_resource_history,
    "propose_change": propose_change,
    "apply_change": apply_change,
    "get_funnel_summary": get_funnel_summary,
    "add_deal": add_deal,
    "delete_deal": delete_deal,
    "get_funnel_history": get_funnel_history,
    "calculate_duration": calculate_duration,
}