"""The schema: current state (Resource) + append-only change log (ResourceHistory)."""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, Date, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Resource(Base):
    __tablename__ = "resources"
    emp_id = Column(Integer, primary_key=True)
    resource_name = Column(String, nullable=False)
    job_title = Column(String)
    line_manager = Column(String)
    line_manager_id = Column(Integer)
    practice = Column(String)
    sub_practice = Column(String)
    grade = Column(String)
    employee_type = Column(String)
    project_client_squad = Column(String)
    billable_flag = Column(Boolean)
    billable_pct = Column(Float)
    daily_rate_usd = Column(Float)
    days_billed = Column(Float)
    monthly_billing_usd = Column(Float)
    engagement_start = Column(Date)
    release_date = Column(Date)
    resource_status = Column(String)
    hire_date = Column(Date)
    hrbp = Column(String)
    department = Column(String)
    location_name = Column(String)
    email_address = Column(String)
    comments = Column(Text)
    data_flag = Column(String)
    loaded_at = Column(DateTime, default=datetime.utcnow)

class ResourceHistory(Base):
    __tablename__ = "resource_history"
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(Integer, nullable=False)
    field_name = Column(String, nullable=False)
    old_value = Column(String)
    new_value = Column(String)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String, nullable=False)


class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_project = Column(String, nullable=False)
    stage = Column(String, nullable=False)  # e.g. Prospecting, Proposal, Won
    probability = Column(Float, nullable=False)  # e.g. 70.0 for 70%
    role = Column(String, nullable=False)  # e.g. Data Engineer, BI, DBA, Other
    quantity = Column(Integer, nullable=False)
    target_month = Column(String, nullable=False)  # format YYYY-MM
    practice = Column(String, nullable=False)  # e.g. Analytics & Insights
    notes = Column(Text)


class DealHistory(Base):
    __tablename__ = "deal_history"
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(Integer, nullable=True)
    deal_name = Column(String)
    action = Column(String, nullable=False)  # created, updated, deleted
    field_name = Column(String)
    old_value = Column(String)
    new_value = Column(String)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String, nullable=False)


class FunnelSnapshot(Base):
    __tablename__ = "funnel_snapshots"
    snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(Integer, nullable=True)
    client_project = Column(String)
    role = Column(String)
    quantity = Column(Integer)
    shortfall = Column(Integer)
    suggested_matches = Column(Text)
    recommendation = Column(Text)
    filters_json = Column(Text)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)