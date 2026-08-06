"""FastAPI server serving the front-end and handling WebSocket connections for the chatbot.
   Run with: python -m uvicorn app.server:app --port 8000 --reload"""

import os
import json
import asyncio
from datetime import date, datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from app.chatbot.agents import ask_stream
from app.db import get_session
from app.models import Resource, Deal
from app.history import log_change, get_history
from app.etl import (
    append_resource_to_excel, sync_from_excel, reconcile_missing_resources_to_excel,
    DEFAULT_EXCEL_PATH, normalize_employee_type, remove_resource_from_excel,
    sync_deals_from_excel, append_deal_to_excel, reconcile_missing_deals_to_excel,
    remove_deal_from_excel,
)
from app.funnel_history import (
    log_deal_created, log_deal_updated, log_deal_deleted,
    log_funnel_snapshots, get_deal_history, get_funnel_snapshots,
)

EXCEL_POLL_INTERVAL_SECONDS = 20

async def _excel_poll_loop():
    """Background task: watches the source Excel file for edits made outside
    the app (e.g. someone editing it directly) and pulls them into the
    database automatically, so no one has to run scripts/run_sync.py by hand."""
    from app.etl import DISABLE_EXCEL_SYNC
    if DISABLE_EXCEL_SYNC:
        print("Excel sync is disabled. Skipping background poll loop.")
        return
    if not os.path.exists(DEFAULT_EXCEL_PATH):
        print(f"Excel file not found at {DEFAULT_EXCEL_PATH}. Skipping background poll loop.")
        return

    last_mtime = None
    while True:
        await asyncio.sleep(EXCEL_POLL_INTERVAL_SECONDS)
        try:
            mtime = os.path.getmtime(DEFAULT_EXCEL_PATH)
        except OSError as e:
            print(f"Excel poll: couldn't stat file: {e}")
            continue

        if mtime != last_mtime:
            try:
                await asyncio.to_thread(sync_from_excel, DEFAULT_EXCEL_PATH, "auto_poll")
            except Exception as e:
                print(f"Excel poll: sync failed: {e}")
            try:
                await asyncio.to_thread(sync_deals_from_excel, DEFAULT_EXCEL_PATH, "auto_poll")
            except Exception as e:
                print(f"Excel poll: Funnel sheet sync failed: {e}")
            last_mtime = mtime

        # Runs every tick regardless of Excel's mtime -- the gap this heals
        # (a DB resource missing from Excel) originates from the DB side
        # (e.g. a transient append failure at creation time), not an Excel edit.
        try:
            fixed = await asyncio.to_thread(reconcile_missing_resources_to_excel, DEFAULT_EXCEL_PATH)
            if fixed:
                print(f"Excel poll: reconciled {fixed} resource(s) missing from Excel")
        except Exception as e:
            print(f"Excel poll: reconciliation failed: {e}")

        try:
            fixed = await asyncio.to_thread(reconcile_missing_deals_to_excel, DEFAULT_EXCEL_PATH)
            if fixed:
                print(f"Excel poll: reconciled {fixed} deal(s) missing from Excel")
        except Exception as e:
            print(f"Excel poll: deal reconciliation failed: {e}")

app = FastAPI(title="Jazz Resource Platform Chatbot Server")

# Configure CORS for local development (React dev server runs on port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get path of frontend build directory
DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

# Mount assets folder
app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

@app.on_event("startup")
async def start_excel_poll_loop():
    asyncio.create_task(_excel_poll_loop())

# Startup database initialization and seeding of mock deals
@app.on_event("startup")
def on_startup():
    from app.models import Base
    from app.db import engine
    from app.chatbot.agents import CLIENTS
    
    # Print warning if Gemini keys are missing
    if not CLIENTS:
        print("\n" + "="*80)
        print("WARNING: No Gemini API key is configured. Chatbot features will not work.")
        print("Please configure GEMINI_API_KEY in your .env file or environment variables.")
        print("="*80 + "\n")
    from app.db import engine
    Base.metadata.create_all(engine)
    
    with get_session() as session:
        if session.query(Deal).count() == 0:
            sample_deals = [
                Deal(client_project="ClientCo - RPA Migration", stage="Proposal", probability=70.0, role="Data Engineer", quantity=3, target_month="2026-07", practice="Analytics & Insights", notes="Awaiting approval from ClientCo leadership."),
                Deal(client_project="ClientCo - BI Dashboarding", stage="Prospecting", probability=40.0, role="BI", quantity=2, target_month="2026-07", practice="Analytics & Insights", notes="Initial discovery calls done."),
                Deal(client_project="ClientCo - Cloud Migration", stage="Won", probability=100.0, role="Data Engineer", quantity=1, target_month="2026-08", practice="Analytics & Insights", notes="Contract signed. Kickoff next month."),
                Deal(client_project="ClientCo - Database Audit", stage="Proposal", probability=60.0, role="DBA", quantity=1, target_month="2026-07", practice="Analytics & Insights", notes="Requires DBA for migration audit."),
                Deal(client_project="ClientCo - Software Scale", stage="Proposal", probability=80.0, role="Other", quantity=2, target_month="2026-08", practice="Software - TSF", notes="Scaling up the frontend team."),
                Deal(client_project="ClientCo - Data Pipeline Integration", stage="Proposal", probability=50.0, role="Data Engineer", quantity=2, target_month="2026-07", practice="Analytics & Insights", notes="Discussing scope.")
            ]
            session.add_all(sample_deals)
            session.commit()
            print("Seeded default sales pipeline deals in database.")

# Helpers for benched resource matching
def get_benched_resources(session):
    resources = session.query(Resource).all()
    benched = []
    for r in resources:
        proj = (r.project_client_squad or "").strip()
        if not proj or proj.lower() == "clientco" or "hq" in proj.lower():
            benched.append(r)
    return benched

def match_role(resource, role):
    title = (resource.job_title or "").lower()
    sub_practice = (resource.sub_practice or "").lower()
    if role == "Data Engineer":
        return "data engineer" in title or "data engineering" in sub_practice or "analytics engineer" in title
    elif role == "BI":
        return "bi" in title or "business intelligence" in sub_practice or "bi" in sub_practice
    elif role == "DBA":
        return "dba" in title or "database" in title or "database" in sub_practice
    elif role == "Other":
        is_de = "data engineer" in title or "data engineering" in sub_practice or "analytics engineer" in title
        is_bi = "bi" in title or "business intelligence" in sub_practice or "bi" in sub_practice
        is_dba = "dba" in title or "database" in title or "database" in sub_practice
        return not (is_de or is_bi or is_dba)
    return False

# Pydantic schemas for Deal API
class DealCreate(BaseModel):
    client_project: str
    stage: str
    probability: float
    role: str
    quantity: int
    target_month: str
    practice: str
    notes: Optional[str] = None

class DealUpdate(BaseModel):
    client_project: Optional[str] = None
    stage: Optional[str] = None
    probability: Optional[float] = None
    role: Optional[str] = None
    quantity: Optional[int] = None
    target_month: Optional[str] = None
    practice: Optional[str] = None
    notes: Optional[str] = None

class ResourceCreate(BaseModel):
    emp_id: int
    resource_name: str
    job_title: Optional[str] = None
    line_manager: Optional[str] = None
    line_manager_id: Optional[int] = None
    practice: Optional[str] = None
    sub_practice: Optional[str] = None
    grade: Optional[str] = None
    employee_type: Optional[str] = None
    project_client_squad: Optional[str] = None
    billable_flag: Optional[bool] = None
    billable_pct: Optional[float] = None
    daily_rate_usd: Optional[float] = None
    days_billed: Optional[float] = None
    monthly_billing_usd: Optional[float] = None
    engagement_start: Optional[date] = None
    release_date: Optional[date] = None
    resource_status: Optional[str] = None
    hire_date: Optional[date] = None
    hrbp: Optional[str] = None
    department: Optional[str] = None
    location_name: Optional[str] = None
    email_address: Optional[str] = None
    comments: Optional[str] = None

class ResourceDeleteResponse(BaseModel):
    status: str
    emp_id: int
    message: Optional[str] = None

# REST Endpoints for Sales & Hiring Funnel
@app.get("/api/choices")
def get_choices():
    with get_session() as session:
        # Get distinct practices from Resource
        res_practices = [p[0] for p in session.query(Resource.practice).distinct().all() if p[0]]
        # Get distinct practices from Deal
        deal_practices = [p[0] for p in session.query(Deal.practice).distinct().all() if p[0]]
        practices = sorted(list(set(res_practices + deal_practices)))
        
        # Get distinct target months from Deal
        months = [m[0] for m in session.query(Deal.target_month).distinct().all() if m[0]]
        if not months:
            months = ["2026-07", "2026-08", "2026-09"]
        else:
            months = sorted(list(set(months)))
            
        return {
            "stages": ["Prospecting", "Proposal", "Won"],
            "roles": ["Data Engineer", "BI", "DBA", "Other"],
            "practices": practices,
            "months": months
        }

@app.get("/api/deals")
def get_deals(
    month: Optional[str] = None,
    role: Optional[str] = None,
    practice: Optional[str] = None,
    stage: Optional[str] = None,
    probability_floor: Optional[float] = None
):
    with get_session() as session:
        query = session.query(Deal)
        if month:
            query = query.filter(Deal.target_month == month)
        if role:
            query = query.filter(Deal.role == role)
        if practice:
            query = query.filter(Deal.practice == practice)
        if stage:
            query = query.filter(Deal.stage == stage)
        if probability_floor is not None:
            query = query.filter(Deal.probability >= probability_floor)
            
        deals = query.all()
        return [
            {
                "id": d.id,
                "client_project": d.client_project,
                "stage": d.stage,
                "probability": d.probability,
                "role": d.role,
                "quantity": d.quantity,
                "target_month": d.target_month,
                "practice": d.practice,
                "notes": d.notes
            }
            for d in deals
        ]

@app.post("/api/deals")
def create_deal(deal: DealCreate):
    with get_session() as session:
        db_deal = Deal(
            client_project=deal.client_project,
            stage=deal.stage,
            probability=deal.probability,
            role=deal.role,
            quantity=deal.quantity,
            target_month=deal.target_month,
            practice=deal.practice,
            notes=deal.notes
        )
        session.add(db_deal)
        session.commit()
        session.refresh(db_deal)
        log_deal_created(session, db_deal, source="api")
        session.commit()

        excel_synced = True
        try:
            append_deal_to_excel({
                "client_project": db_deal.client_project,
                "stage": db_deal.stage,
                "probability": db_deal.probability,
                "role": db_deal.role,
                "quantity": db_deal.quantity,
                "target_month": db_deal.target_month,
                "practice": db_deal.practice,
                "notes": db_deal.notes,
            })
        except Exception as e:
            print(f"Excel append failed for deal id {db_deal.id}: {e}")
            excel_synced = False

        return {"status": "success", "id": db_deal.id, "excel_synced": excel_synced}

@app.put("/api/deals/{deal_id}")
def update_deal(deal_id: int, update_data: DealUpdate):
    with get_session() as session:
        db_deal = session.get(Deal, deal_id)
        if not db_deal:
            raise HTTPException(status_code=404, detail="Deal not found")
        for field, value in update_data.dict(exclude_unset=True).items():
            old_value = getattr(db_deal, field)
            if old_value != value:
                log_deal_updated(session, db_deal, field, old_value, value, source="api")
            setattr(db_deal, field, value)
        session.commit()
        return {"status": "success"}

@app.delete("/api/deals/{deal_id}")
def delete_deal(deal_id: int):
    with get_session() as session:
        db_deal = session.get(Deal, deal_id)
        if not db_deal:
            raise HTTPException(status_code=404, detail="Deal not found")
        client_project, role, target_month = db_deal.client_project, db_deal.role, db_deal.target_month
        log_deal_deleted(session, db_deal, source="api")
        session.delete(db_deal)
        session.commit()

        try:
            remove_deal_from_excel(client_project, role, target_month)
        except Exception as e:
            print(f"Excel removal failed for deal id {deal_id}: {e}")

        return {"status": "success"}

@app.get("/api/resources")
def get_resources():
    with get_session() as session:
        resources = session.query(Resource).all()
        return [
            {
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
                "engagement_start": r.engagement_start.isoformat() if r.engagement_start else None,
                "release_date": r.release_date.isoformat() if r.release_date else None,
                "resource_status": r.resource_status,
                "hire_date": r.hire_date.isoformat() if r.hire_date else None,
                "hrbp": r.hrbp,
                "department": r.department,
                "location_name": r.location_name,
                "email_address": r.email_address,
                "comments": r.comments,
                "data_flag": r.data_flag,
                "loaded_at": r.loaded_at.isoformat() if r.loaded_at else None,
            }
            for r in resources
        ]

@app.post("/api/resources")
def create_resource(resource: ResourceCreate):
    with get_session() as session:
        existing = session.get(Resource, resource.emp_id)
        if existing:
            raise HTTPException(status_code=409, detail="Resource with this emp_id already exists")

        db_resource = Resource(
            emp_id=resource.emp_id,
            resource_name=resource.resource_name,
            job_title=resource.job_title,
            line_manager=resource.line_manager,
            line_manager_id=resource.line_manager_id,
            practice=resource.practice,
            sub_practice=resource.sub_practice,
            grade=resource.grade,
            employee_type=normalize_employee_type(resource.employee_type),
            project_client_squad=resource.project_client_squad,
            billable_flag=resource.billable_flag,
            billable_pct=resource.billable_pct,
            daily_rate_usd=resource.daily_rate_usd,
            days_billed=resource.days_billed,
            monthly_billing_usd=resource.monthly_billing_usd,
            engagement_start=resource.engagement_start,
            release_date=resource.release_date,
            resource_status=resource.resource_status,
            hire_date=resource.hire_date,
            hrbp=resource.hrbp,
            department=resource.department,
            location_name=resource.location_name,
            email_address=resource.email_address,
            comments=resource.comments,
            data_flag=None,
            loaded_at=datetime.utcnow()
        )
        session.add(db_resource)
        session.commit()
        log_change(session, db_resource.emp_id, "record", None, "created", "api")
        session.commit()

        excel_synced = True
        try:
            append_resource_to_excel({
                "emp_id": db_resource.emp_id,
                "resource_name": db_resource.resource_name,
                "job_title": db_resource.job_title,
                "line_manager": db_resource.line_manager,
                "line_manager_id": db_resource.line_manager_id,
                "practice": db_resource.practice,
                "sub_practice": db_resource.sub_practice,
                "grade": db_resource.grade,
                "employee_type": db_resource.employee_type,
                "project_client_squad": db_resource.project_client_squad,
                "billable_flag": db_resource.billable_flag,
                "billable_pct": db_resource.billable_pct,
                "daily_rate_usd": db_resource.daily_rate_usd,
                "days_billed": db_resource.days_billed,
                "monthly_billing_usd": db_resource.monthly_billing_usd,
                "engagement_start": db_resource.engagement_start,
                "release_date": db_resource.release_date,
                "resource_status": db_resource.resource_status,
                "hire_date": db_resource.hire_date,
                "hrbp": db_resource.hrbp,
                "department": db_resource.department,
                "location_name": db_resource.location_name,
                "email_address": db_resource.email_address,
                "comments": db_resource.comments,
            })
        except Exception as e:
            print(f"Excel append failed for emp_id {db_resource.emp_id}: {e}")
            excel_synced = False

        return {"status": "success", "emp_id": db_resource.emp_id, "excel_synced": excel_synced}

@app.delete("/api/resources/{emp_id}")
def delete_resource(emp_id: int):
    with get_session() as session:
        db_resource = session.get(Resource, emp_id)
        if not db_resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        log_change(session, emp_id, "record", None, "deleted", "api")
        session.delete(db_resource)
        session.commit()

        try:
            remove_resource_from_excel(emp_id)
        except Exception as e:
            print(f"Excel removal failed for emp_id {emp_id}: {e}")

        return {"status": "success", "emp_id": emp_id}

@app.get("/api/resources/{emp_id}/history")
def get_resource_history_route(emp_id: int):
    with get_session() as session:
        rows = get_history(session, emp_id)
        return [
            {
                "history_id": h.history_id,
                "emp_id": h.emp_id,
                "field_name": h.field_name,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "changed_at": h.changed_at.isoformat(),
                "source": h.source,
            }
            for h in rows
        ]

@app.get("/api/funnel")
def get_funnel(
    month: Optional[str] = None,
    role: Optional[str] = None,
    practice: Optional[str] = None,
    stage: Optional[str] = None,
    probability_floor: Optional[float] = None
):
    with get_session() as session:
        query = session.query(Deal)
        if month:
            query = query.filter(Deal.target_month == month)
        if role:
            query = query.filter(Deal.role == role)
        if practice:
            query = query.filter(Deal.practice == practice)
        if stage:
            query = query.filter(Deal.stage == stage)
        if probability_floor is not None:
            query = query.filter(Deal.probability >= probability_floor)
            
        deals = query.all()
        benched = get_benched_resources(session)
        
        cautious_estimate = 0.0
        hopeful_estimate = 0.0
        deal_recommendations = []
        
        benched_by_role = {"Data Engineer": [], "BI": [], "DBA": [], "Other": []}
        for r in benched:
            for role_name in benched_by_role.keys():
                if match_role(r, role_name):
                    benched_by_role[role_name].append({
                        "emp_id": r.emp_id,
                        "resource_name": r.resource_name,
                        "job_title": r.job_title,
                        "grade": r.grade,
                        "employee_type": r.employee_type,
                        "practice": r.practice,
                        "sub_practice": r.sub_practice,
                        "location_name": r.location_name
                    })
                    break
                    
        for d in deals:
            expected_demand = d.quantity * (d.probability / 100.0)
            hopeful_estimate += expected_demand
            if d.probability >= 70.0:
                cautious_estimate += expected_demand
                
            matching_benched = []
            for r in benched:
                if match_role(r, d.role):
                    matching_benched.append(r)
                    
            # Prioritize matching practice
            matching_benched.sort(key=lambda r: 0 if (r.practice or "").lower() == (d.practice or "").lower() else 1)
            
            suggested = matching_benched[:d.quantity]
            suggested_names = [
                f"{s.resource_name} ({s.grade or '?'}, {s.location_name or '?'})"
                for s in suggested
            ]
            shortfall = max(0, d.quantity - len(suggested))
            
            if shortfall == 0:
                recommendation = f"Fully staffed. Suggested benched matches: {', '.join(suggested_names)}."
            else:
                matches_str = f"Suggested benched matches: {', '.join(suggested_names)}." if suggested_names else "No matching benched resources."
                recommendation = f"{matches_str} Shortfall of {shortfall} {d.role}(s). Recommendation: Hire {shortfall} {d.role}(s)."
                
            deal_recommendations.append({
                "id": d.id,
                "client_project": d.client_project,
                "stage": d.stage,
                "probability": d.probability,
                "role": d.role,
                "quantity": d.quantity,
                "target_month": d.target_month,
                "practice": d.practice,
                "expected_demand": round(expected_demand, 2),
                "suggested_matches": suggested_names,
                "shortfall": shortfall,
                "recommendation": recommendation
            })

        active_filters = {
            "month": month,
            "role": role,
            "practice": practice,
            "stage": stage,
            "probability_floor": probability_floor,
        }
        log_funnel_snapshots(session, deal_recommendations, active_filters)
        session.commit()
            
        return {
            "cautious_estimate": round(cautious_estimate, 2),
            "hopeful_estimate": round(hopeful_estimate, 2),
            "recommendations": deal_recommendations,
            "benched": benched_by_role
        }

@app.get("/api/deals/history")
def get_deals_history(deal_id: Optional[int] = None, limit: int = Query(default=50, le=200)):
    import json as _json
    with get_session() as session:
        rows = get_deal_history(session, deal_id=deal_id, limit=limit)
        return [
            {
                "history_id": h.history_id,
                "deal_id": h.deal_id,
                "deal_name": h.deal_name,
                "action": h.action,
                "field_name": h.field_name,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "changed_at": h.changed_at.isoformat(),
                "source": h.source,
            }
            for h in rows
        ]

@app.get("/api/funnel/history")
def get_funnel_history(deal_id: Optional[int] = None, limit: int = Query(default=50, le=200)):
    import json as _json
    with get_session() as session:
        rows = get_funnel_snapshots(session, deal_id=deal_id, limit=limit)
        return [
            {
                "snapshot_id": s.snapshot_id,
                "deal_id": s.deal_id,
                "client_project": s.client_project,
                "role": s.role,
                "quantity": s.quantity,
                "shortfall": s.shortfall,
                "suggested_matches": _json.loads(s.suggested_matches or "[]"),
                "recommendation": s.recommendation,
                "filters": _json.loads(s.filters_json or "{}"),
                "computed_at": s.computed_at.isoformat(),
            }
            for s in rows
        ]

@app.get("/api/overview")
def get_overview():
    """Aggregated workforce-health metrics. Pure read, no side effects."""
    GRADE_ORDER = ["L1", "L2", "L3", "L4", "L5"]

    with get_session() as session:
        resources = session.query(Resource).all()
        headcount = len(resources)
        benched = get_benched_resources(session)
        bench_ids = {r.emp_id for r in benched}

        billable_count = sum(1 for r in resources if r.billable_flag)
        total_monthly_billing = sum(
            r.monthly_billing_usd if r.monthly_billing_usd is not None 
            else ((r.daily_rate_usd or 0) * 20) if r.billable_flag else 0 
            for r in resources
        )
        rates = [r.daily_rate_usd for r in resources if r.daily_rate_usd]
        avg_daily_rate = round(sum(rates) / len(rates)) if rates else 0
        flagged_count = sum(1 for r in resources if r.data_flag)

        # Per-practice rollup
        practices = {}
        for r in resources:
            key = r.practice or "Unspecified"
            p = practices.setdefault(key, {"practice": key, "headcount": 0,
                                           "billable": 0, "benched": 0, "monthly_billing": 0})
            p["headcount"] += 1
            if r.billable_flag:
                p["billable"] += 1
            if r.emp_id in bench_ids:
                p["benched"] += 1
            billing_val = r.monthly_billing_usd if r.monthly_billing_usd is not None else ((r.daily_rate_usd or 0) * 20) if r.billable_flag else 0
            p["monthly_billing"] += billing_val
        by_practice = sorted(practices.values(), key=lambda x: x["headcount"], reverse=True)
        for p in by_practice:
            p["monthly_billing"] = round(p["monthly_billing"])

        # Per-location rollup
        locations = {}
        for r in resources:
            key = r.location_name or "Unspecified"
            l = locations.setdefault(key, {"location": key, "headcount": 0, "benched": 0})
            l["headcount"] += 1
            if r.emp_id in bench_ids:
                l["benched"] += 1
        by_location = sorted(locations.values(), key=lambda x: x["headcount"], reverse=True)

        # Per-department rollup
        departments = {}
        for r in resources:
            key = r.department or "Unspecified"
            d = departments.setdefault(key, {"department": key, "headcount": 0})
            d["headcount"] += 1
        by_department = sorted(departments.values(), key=lambda x: x["headcount"], reverse=True)

        # Active projects count
        active_projects = set()
        for r in resources:
            if r.emp_id not in bench_ids and r.project_client_squad:
                proj = r.project_client_squad.strip()
                if proj and proj.lower() != "clientco" and "hq" not in proj.lower():
                    active_projects.add(proj)
        active_projects_count = len(active_projects)

        # Grade distribution -- L1..L5 only; stray non-grade values (data-entry
        # errors like an employee_type leaking into this column, or blanks)
        # are excluded rather than shown as their own bogus bar.
        grades = {}
        for r in resources:
            if r.grade in GRADE_ORDER:
                grades[r.grade] = grades.get(r.grade, 0) + 1
        by_grade = [{"grade": g, "count": grades[g]} for g in GRADE_ORDER if g in grades]

        # Employee type distribution (Full-Time Regular, Contractual, Probationary, etc.)
        emp_types = {}
        for r in resources:
            key = r.employee_type or "Unspecified"
            emp_types[key] = emp_types.get(key, 0) + 1
        by_employee_type = [{"employee_type": k, "count": v}
                            for k, v in sorted(emp_types.items(), key=lambda x: x[1], reverse=True)]

        # Data-quality flag counts (data_flag is comma-joined)
        flag_counts = {}
        for r in resources:
            if r.data_flag:
                for f in r.data_flag.split(","):
                    f = f.strip()
                    if f:
                        flag_counts[f] = flag_counts.get(f, 0) + 1
        flags = [{"flag": f, "count": c} for f, c in
                 sorted(flag_counts.items(), key=lambda x: x[1], reverse=True)]

        return {
            "headcount": headcount,
            "billable_count": billable_count,
            "bench_count": len(benched),
            "bench_rate": round(len(benched) / headcount * 100, 1) if headcount else 0,
            "total_monthly_billing": round(total_monthly_billing),
            "avg_daily_rate": avg_daily_rate,
            "flagged_count": flagged_count,
            "active_projects_count": active_projects_count,
            "by_practice": by_practice,
            "by_location": by_location,
            "by_department": by_department,
            "by_grade": by_grade,
            "by_employee_type": by_employee_type,
            "flags": flags,
        }


def _month_bounds(offset):
    """Bounds for the month `offset` months back from today (offset=0 → current
    month, offset=-1 → next month, etc). Returns (first_day, last_day, label)."""
    from calendar import monthrange
    today = date.today()
    year, month = today.year, today.month - offset
    while month <= 0:
        month += 12
        year  -= 1
    while month > 12:
        month -= 12
        year  += 1
    last_day  = date(year, month, monthrange(year, month)[1])
    first_day = date(year, month, 1)
    return first_day, last_day, last_day.strftime("%b %Y")


def _history_month_offsets(as_of_date=None):
    """Return month offsets for the last 12 fully completed months.

    If today is not the last day of the month, the current month is treated as
    incomplete and excluded so forecasting is driven by fully completed history
    only.
    """
    from calendar import monthrange

    today = as_of_date or date.today()
    last_day = monthrange(today.year, today.month)[1]
    is_complete_month = today.day == last_day
    if is_complete_month:
        return list(range(11, -1, -1))
    return list(range(12, 0, -1))


def _metrics_for_month(resources, first_day, last_day):
    """Headcount/billable/benched/revenue as of a given month, derived from
    hire_date/billable_flag/release_date (same rule used historically and for
    forecasting, so the two stay directly comparable).

    billable_flag alone decides billable status -- matching /api/overview's
    billable_count definition -- rather than also requiring engagement_start.
    engagement_start is only populated for ~20% of resources, so requiring it
    here used to undercount billable staff by roughly 4x versus /api/overview's
    own KPI tile (34 vs 155 on the current dataset), which silently inflated
    "benched" in the Utilization Trend chart and the workforce forecast."""
    # Headcount = everyone hired on or before end of this month
    active = [r for r in resources
              if r.hire_date and r.hire_date <= last_day]
    headcount = len(active)

    # Billable = hired, flagged billable, not yet released by month start
    billable_list = [
        r for r in active
        if r.billable_flag
        and (not r.release_date or r.release_date > first_day)
    ]
    billable = len(billable_list)
    benched  = headcount - billable
    revenue  = round(sum(
        r.monthly_billing_usd if r.monthly_billing_usd is not None 
        else ((r.daily_rate_usd or 0) * 20) 
        for r in billable_list
    ))
    return {"headcount": headcount, "billable": billable, "benched": benched, "revenue": revenue}


@app.get("/api/overview/timeseries")
def get_overview_timeseries():
    """12-month historical workforce metrics derived from hire_date and engagement_start."""
    with get_session() as session:
        resources = session.query(Resource).all()
        result = []
        for month_offset in _history_month_offsets():   # oldest first → most recent completed month
            first_day, last_day, label = _month_bounds(month_offset)
            result.append({"month": label, **_metrics_for_month(resources, first_day, last_day)})
        return result


def _project_workforce_metrics(
    resources, 
    months, 
    win_probability_floor=50.0, 
    attrition_rate=0.0, 
    trend_scalar=1.0, 
    daily_rate_scaler=1.0, 
    model_type="hybrid", 
    session=None
):
    """Upgraded forecast engine: projects workforce metrics combining OLS trend lines,
    turnover attrition, scheduled releases, and active pipeline deals.
    """
    import numpy as np

    # 1. Gather the last 12 fully completed months as baseline
    history = []
    for month_offset in _history_month_offsets():
        first_day, last_day, label = _month_bounds(month_offset)
        history.append({"month": label, **_metrics_for_month(resources, first_day, last_day)})

    n = len(history)
    x = np.arange(n, dtype=float)
    x_mean = float(x.mean())
    sxx = float(np.sum((x - x_mean) ** 2))

    # Fit historical metrics using Holt's Linear Exponential Smoothing
    def fit_metric(key):
        y = np.array([h[key] for h in history], dtype=float)
        all_zero = bool(np.all(y == 0))
        if all_zero:
            return {"slope": 0.0, "intercept": 0.0, "resid_std": 0.0, "r_squared": None,
                    "low_confidence": True, "flat_trend": True, "all_zero": True}

        # Holt's linear smoothing algorithm (alpha=0.5, beta=0.3)
        alpha, beta = 0.5, 0.3
        
        # Initialize level and trend with first 3 points linear fit
        slope, intercept = np.polyfit(np.arange(min(n, 3)), y[:min(n, 3)], 1)
        level = intercept
        trend = slope
        
        fitted = []
        for i in range(n):
            if i == 0:
                y_hat = level
            else:
                y_hat = level + trend
            fitted.append(y_hat)
            
            y_i = float(y[i])
            last_level = level
            level = alpha * y_i + (1.0 - alpha) * (level + trend)
            trend = beta * (level - last_level) + (1.0 - beta) * trend
            
        fitted = np.array(fitted)
        resid = y - fitted
        ss_res = float(np.sum(resid ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r_squared = None if ss_tot == 0 else 1.0 - ss_res / ss_tot
        resid_std = float(np.sqrt(ss_res / (n - 2))) if n > 2 else 0.0
        mean_y = float(y.mean())
        
        # Holt's specific slope and intercept mapping:
        # We define intercept such that slope * (n - 1 + step) + intercept = level + step * trend
        compat_slope = trend
        compat_intercept = level - (n - 1) * trend
        
        flat_trend = bool(mean_y != 0 and abs(trend) < 0.02 * abs(mean_y))
        low_confidence = bool(n < 4 or (r_squared is not None and r_squared < 0.5))

        return {"slope": float(compat_slope), "intercept": float(compat_intercept), "resid_std": resid_std,
                "r_squared": r_squared, "low_confidence": low_confidence,
                "flat_trend": flat_trend, "all_zero": False}

    fits = {key: fit_metric(key) for key in ("headcount", "billable", "revenue")}
    Z = 1.28  # 80% confidence interval multiplier

    # Pre-calculate role rates for staffing simulation
    roles = ["Data Engineer", "BI", "DBA", "Other"]
    role_rates = {}
    for r_name in roles:
        rates = [r.daily_rate_usd for r in resources if r.daily_rate_usd and match_role(r, r_name)]
        role_rates[r_name] = sum(rates) / len(rates) if rates else 144.0

    # Initialize benched pool states from current active bench resources
    benched_pool = get_benched_resources(session) if session else []
    bench_pools = {r_name: 0 for r_name in roles}
    for r in benched_pool:
        for r_name in roles:
            if match_role(r, r_name):
                bench_pools[r_name] += 1
                break

    # Simulated forecast state starting from current actuals
    hc_sim = float(history[-1]["headcount"])
    bill_sim = float(history[-1]["billable"])
    rev_sim = float(history[-1]["revenue"])

    forecast = []
    for step in range(1, months + 1):
        x0 = n - 1 + step
        first_day, last_day, label = _month_bounds(-step)

        # Baseline trend increment
        if model_type == "ols":
            # Strict OLS
            y_hat_hc = fits["headcount"]["slope"] * x0 + fits["headcount"]["intercept"]
            y_hat_bill = fits["billable"]["slope"] * x0 + fits["billable"]["intercept"]
            y_hat_rev = fits["revenue"]["slope"] * x0 + fits["revenue"]["intercept"]
            
            # Apply adjustments to OLS directly
            hc_sim = max(0.0, y_hat_hc + fits["headcount"]["slope"] * (trend_scalar - 1.0) * step)
            bill_sim = max(0.0, y_hat_bill + fits["billable"]["slope"] * (trend_scalar - 1.0) * step)
            rev_sim = max(0.0, y_hat_rev + fits["revenue"]["slope"] * (trend_scalar - 1.0) * step)
            
            hc_sim *= (1.0 - attrition_rate / 100.0) ** step
            bill_sim *= (1.0 - attrition_rate / 100.0) ** step
            rev_sim *= (1.0 - attrition_rate / 100.0) ** step * daily_rate_scaler
            bill_sim = min(bill_sim, hc_sim)
            bench_sim = max(0.0, hc_sim - bill_sim)
        else:
            # Hybrid or Pipeline-Only
            dh_bg = fits["headcount"]["slope"] * trend_scalar if model_type == "hybrid" else 0.0
            db_bg = fits["billable"]["slope"] * trend_scalar if model_type == "hybrid" else 0.0
            dr_bg = fits["revenue"]["slope"] * trend_scalar if model_type == "hybrid" else 0.0

            # Attrition
            hc_attr = hc_sim * (attrition_rate / 100.0)
            bill_attr = bill_sim * (attrition_rate / 100.0)
            rev_attr = rev_sim * (attrition_rate / 100.0)

            # Scheduled releases
            released_in_month = [
                r for r in resources 
                if r.billable_flag and r.release_date and first_day <= r.release_date <= last_day
            ]
            released_count = len(released_in_month)
            released_rev = sum(
                r.monthly_billing_usd if r.monthly_billing_usd is not None 
                else ((r.daily_rate_usd or 0) * 20) 
                for r in released_in_month
            )

            # Add rolled-off resources back to specialized bench pools
            for r in released_in_month:
                for r_name in roles:
                    if match_role(r, r_name):
                        bench_pools[r_name] += 1
                        break

            # Pipeline deals targeting this month
            target_month_str = first_day.strftime("%Y-%m")
            deals_in_month = []
            if session:
                deals_in_month = (
                    session.query(Deal)
                    .filter(Deal.target_month == target_month_str, Deal.probability >= win_probability_floor)
                    .all()
                )

            # Sum demand by role
            demand_by_role = {r_name: 0.0 for r_name in roles}
            for d in deals_in_month:
                demand_by_role[d.role] = demand_by_role.get(d.role, 0.0) + d.quantity * (d.probability / 100.0)

            # Match against bench and determine hiring shortfall
            shortfalls = {r_name: 0.0 for r_name in roles}
            placements = {r_name: 0.0 for r_name in roles}
            for r_name in roles:
                D = demand_by_role[r_name]
                U = bench_pools[r_name]
                placed = min(D, U)
                shortfall = D - placed
                
                bench_pools[r_name] = U - placed
                placements[r_name] = placed
                shortfalls[r_name] = shortfall

            total_shortfalls = sum(shortfalls.values())
            total_placements = sum(placements.values())
            total_pipeline_billable_added = total_placements + total_shortfalls

            pipeline_revenue_added = sum(
                demand_by_role[r_name] * role_rates[r_name] * 20 * daily_rate_scaler 
                for r_name in roles
            )
            pipeline_revenue_lost = released_rev * daily_rate_scaler
            pipeline_rev_change = pipeline_revenue_added - pipeline_revenue_lost

            # Apply state updates
            hc_sim = hc_sim + dh_bg - hc_attr + total_shortfalls
            bill_sim = bill_sim + db_bg - bill_attr - released_count + total_pipeline_billable_added
            hc_sim = max(0.0, hc_sim)
            bill_sim = max(0.0, min(bill_sim, hc_sim))
            bench_sim = max(0.0, hc_sim - bill_sim)
            
            rev_sim = rev_sim + dr_bg - rev_attr + pipeline_rev_change
            rev_sim = max(0.0, rev_sim)

        # Standard errors for prediction bands (based on Holt's forecast variance)
        def get_se(key):
            f = fits[key]
            if f["all_zero"]:
                return 0.0
            
            # Var(e_t(h)) = sigma^2 * [1 + sum_{j=1}^{h-1} (alpha + j * alpha * beta)^2]
            alpha, beta = 0.5, 0.3
            sum_term = 0.0
            for j in range(1, step):
                sum_term += (alpha + j * alpha * beta) ** 2
            return float(f["resid_std"] * np.sqrt(1.0 + sum_term))

        se_hc = get_se("headcount")
        se_bill = get_se("billable")
        se_rev = get_se("revenue")

        hc_lo = max(0, round(hc_sim - Z * se_hc))
        hc_hi = round(hc_sim + Z * se_hc)
        bill_lo = max(0, round(bill_sim - Z * se_bill))
        bill_hi = round(bill_sim + Z * se_bill)
        bench_lo = max(0, hc_lo - bill_hi)
        bench_hi = max(0, hc_hi - bill_lo)
        rev_lo = max(0, round(rev_sim - Z * se_rev))
        rev_hi = round(rev_sim + Z * se_rev)

        forecast.append({
            "month": label,
            "headcount": round(hc_sim), "headcount_low": hc_lo, "headcount_high": hc_hi,
            "billable": round(bill_sim), "billable_low": bill_lo, "billable_high": bill_hi,
            "benched": round(bench_sim), "benched_low": bench_lo, "benched_high": bench_hi,
            "revenue": round(rev_sim), "revenue_low": rev_lo, "revenue_high": rev_hi,
        })

    metrics_meta = {
        key: {k: v for k, v in f.items() if k in
              ("r_squared", "low_confidence", "flat_trend", "all_zero")}
        for key, f in fits.items()
    }
    metrics_meta["headcount"]["slope"] = fits["headcount"]["slope"]
    metrics_meta["billable"]["slope"] = fits["billable"]["slope"]
    metrics_meta["revenue"]["slope"] = fits["revenue"]["slope"]
    metrics_meta["benched"] = {"derived_from": ["headcount", "billable"]}

    return {"history": history, "forecast": forecast, "history_months_used": n,
            "metrics_meta": metrics_meta}


@app.get("/api/overview/forecast")
def get_overview_forecast(
    months: int = Query(3, ge=1, le=3),
    win_probability_floor: float = Query(50.0, ge=0.0, le=100.0),
    attrition_rate: float = Query(0.0, ge=0.0, le=10.0),
    trend_scalar: float = Query(1.0, ge=-1.0, le=2.0),
    daily_rate_scaler: float = Query(1.0, ge=0.8, le=1.2),
    model_type: str = Query("hybrid")
):
    """History-based projection of workforce metrics using completed historical months. Pure read, no persistence."""
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
            session=session
        )

        return {
            "history": projection["history"],
            "forecast": projection["forecast"],
            "method": model_type,
            "confidence_level": 0.80,
            "history_months_used": projection["history_months_used"],
            "metrics_meta": projection["metrics_meta"],
            "disclaimer": (
                "Projection is a simulation model combining OLS trend, attrition, scheduled releases, and sales pipeline. "
                "Treat it as directional scenario planning."
            ),
        }


def _pipeline_hiring_need(session, month_labels):
    """Hiring shortfall per forecast month, derived from open deals whose
    target_month falls in the forecast window. Deals are processed most-probable
    first, depleting a shared per-role benched pool as they claim matches --
    unlike /api/funnel's per-deal loop, a benched resource claimed by one deal is
    removed from the pool before the next deal checks it, so nobody is counted as
    a match for two deals at once."""
    roles = ["Data Engineer", "BI", "DBA", "Other"]
    benched = get_benched_resources(session)
    deals = session.query(Deal).all()

    # Map each deal's "YYYY-MM" target_month onto the same "%b %Y" labels used by
    # the workforce forecast, so the two can be combined month-for-month.
    deals_by_label = {label: [] for label in month_labels}
    for d in deals:
        try:
            label = datetime.strptime(d.target_month, "%Y-%m").strftime("%b %Y")
        except ValueError:
            continue
        if label in deals_by_label:
            deals_by_label[label].append(d)

    by_month = []
    for label in month_labels:
        month_deals = deals_by_label[label]
        if not month_deals:
            by_month.append({"month": label, "has_data": False, "cautious": 0,
                              "hopeful": 0, "by_role": []})
            continue

        def shortfall_for(deal_subset):
            pool = {role: [r for r in benched if match_role(r, role)] for role in roles}
            role_shortfall = {role: 0 for role in roles}
            for d in sorted(deal_subset, key=lambda d: d.probability, reverse=True):
                available = pool.get(d.role, [])
                claimed = available[:d.quantity]
                del available[:len(claimed)]
                role_shortfall[d.role] = role_shortfall.get(d.role, 0) + max(0, d.quantity - len(claimed))
            return role_shortfall

        hopeful_by_role = shortfall_for(month_deals)
        cautious_by_role = shortfall_for([d for d in month_deals if d.probability >= 70.0])

        by_month.append({
            "month": label,
            "has_data": True,
            "cautious": sum(cautious_by_role.values()),
            "hopeful": sum(hopeful_by_role.values()),
            "by_role": [{"role": role, "shortfall": hopeful_by_role[role]}
                        for role in roles if hopeful_by_role[role] > 0],
        })

    total_deals = len(deals)
    covered_labels = sorted({label for label, ds in deals_by_label.items() if ds})
    return {
        "by_month": by_month,
        "data_note": (
            f"Based on {total_deals} deal(s) in the pipeline; "
            + (f"only {', '.join(covered_labels)} currently have a target month in this window. "
               if covered_labels else "none currently target a month in this window. ")
            + "Months with no deals show no data, not zero demand."
        ),
    }


def _trend_hiring_need(projection, current_bench_count):
    """Speculative hiring need derived from the already-fitted billable trend:
    month-over-month growth in projected billable headcount, netted against
    today's bench pool (depleted across successive months as growth consumes it).
    Does not model attrition -- see disclaimer."""
    history = projection["history"]
    forecast = projection["forecast"]
    remaining_bench = max(0, current_bench_count)

    by_month = []
    prev_billable = history[-1]["billable"] if history else 0
    for point in forecast:
        growth = max(0, point["billable"] - prev_billable)
        covered_by_bench = min(growth, remaining_bench)
        remaining_bench -= covered_by_bench
        recommended = growth - covered_by_bench
        by_month.append({"month": point["month"], "recommended_hires": recommended})
        prev_billable = point["billable"]

    return {
        "by_month": by_month,
        "disclaimer": (
            "Speculative -- extrapolates the 6-month billable trend net of today's "
            "bench pool. Attrition is not modeled: release_date is populated for "
            "only a small fraction of resources today, so real hiring need may be "
            "understated if people leave."
        ),
    }


@app.get("/api/hiring-forecast")
def get_hiring_forecast(months: int = Query(3, ge=1, le=3)):
    """Combines pipeline-driven (deal-based) and trend-driven (workforce-pattern-based)
    hiring need into one view. Pure read, no persistence."""
    with get_session() as session:
        resources = session.query(Resource).all()
        projection = _project_workforce_metrics(resources, months, session=session)
        month_labels = [point["month"] for point in projection["forecast"]]

        pipeline = _pipeline_hiring_need(session, month_labels)
        # Reuse the same headcount/billable rules _metrics_for_month already applies
        # (hire_date/engagement_start/release_date-aware) rather than a cruder count,
        # so "current bench" here matches what /api/overview reports.
        current_bench_count = projection["history"][-1]["benched"] if projection["history"] else 0
        trend = _trend_hiring_need(projection, current_bench_count)

        pipeline_by_month = {m["month"]: m for m in pipeline["by_month"]}
        trend_by_month = {m["month"]: m for m in trend["by_month"]}
        recommended_total_by_month = []
        for label in month_labels:
            p = pipeline_by_month[label]
            t = trend_by_month[label]
            recommended_total_by_month.append({
                "month": label,
                "conservative": p["cautious"] + t["recommended_hires"],
                "upper_bound": p["hopeful"] + t["recommended_hires"],
            })

        return {
            "months": month_labels,
            "pipeline_driven": pipeline,
            "trend_driven": trend,
            "recommended_total_by_month": recommended_total_by_month,
        }


@app.get("/health")
def health_check():
    """Verify server health and database connectivity."""
    from sqlalchemy import text
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )


@app.get("/")
async def get_index():
    """Serve React app index.html at root url"""
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket handler for real-time chatbot interaction"""
    await websocket.accept()
    try:
        while True:
            # Wait for user query
            data = await websocket.receive_text()

            # Scoped to this one turn -- a failure anywhere in here (parsing,
            # generation, sending) must not tear down the whole connection, or
            # every future question on it goes unanswered.
            session_id = None
            try:
                payload = json.loads(data)
                question = payload.get("question", "").strip()
                history = payload.get("history", [])
                # Echoed back on every update so the client can route the reply
                # to the session that asked, even if a different one is on
                # screen by the time it arrives.
                session_id = payload.get("session_id")

                if not question:
                    continue

                async for update in ask_stream(question, history):
                    update["session_id"] = session_id
                    await websocket.send_text(json.dumps(update))
            except Exception as e:
                # Log the real error server-side, but never leak internal/provider
                # error text (stack traces, API payloads, etc.) to the client.
                print(f"Unhandled error processing a chat turn: {e}")
                try:
                    await websocket.send_text(json.dumps({
                        "type": "answer",
                        "content": "Something went wrong while processing your request. Please try again.",
                        "session_id": session_id,
                    }))
                except Exception:
                    pass

    except WebSocketDisconnect:
        # Client closed connection
        pass
