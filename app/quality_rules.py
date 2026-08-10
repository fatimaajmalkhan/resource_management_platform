"""Data quality checks -- add a new rule by adding a function + adding it to RULES."""

def check_missing_hr_fields(row):
    if row.get("job_title") is None and row.get("employee_type") is None:
        return "missing_hr_fields"
    return None

def check_zero_billing_active(row):
    if row.get("monthly_billing_usd") == 0 and row.get("resource_status") == "Active":
        return "zero_billing_active"
    return None

RULES = [check_missing_hr_fields, check_zero_billing_active]

def run_quality_checks(row):
    flags = [f for rule in RULES if (f := rule(row))]
    return ",".join(flags) if flags else None