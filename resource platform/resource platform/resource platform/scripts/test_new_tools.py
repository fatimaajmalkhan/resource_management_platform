"""Standalone test script to test get_resource_by_id() and query_resources() directly against the database.
   Run with: python scripts/test_new_tools.py"""
import sys
import os
import json

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import get_session
from app.models import Resource
from app.chatbot.tools import get_resource_by_id, query_resources

def print_result(title, data):
    print(f"=== {title} ===")
    print(json.dumps(data, indent=2))
    print()

def main():
    # 1. Get first resource from database to get a valid ID for testing
    with get_session() as session:
        r = session.query(Resource).first()
        if not r:
            print("No resources found in database to run tests against.")
            return
        valid_id = r.emp_id
        valid_name = r.resource_name
        valid_practice = r.practice
        valid_grade = r.grade
        print(f"Testing with resource: ID={valid_id}, Name={valid_name}, Practice={valid_practice}, Grade={valid_grade}\n")

    # 2. Test get_resource_by_id (success)
    res_id_success = get_resource_by_id(valid_id)
    print_result("Test get_resource_by_id (Success)", res_id_success)

    # 3. Test get_resource_by_id (failure)
    res_id_fail = get_resource_by_id(999999)
    print_result("Test get_resource_by_id (Failure)", res_id_fail)

    # 4. Test query_resources with filters
    res_query_filter = query_resources(filters={"grade": valid_grade})
    print_result(f"Test query_resources with filters (grade={valid_grade})", res_query_filter)

    # 5. Test query_resources with invalid filter column
    res_query_invalid_filter = query_resources(filters={"invalid_column_name": "value"})
    print_result("Test query_resources with invalid column", res_query_invalid_filter)

    # 6. Test query_resources with aggregate count
    res_query_count = query_resources(filters={"grade": valid_grade}, aggregate="count")
    print_result(f"Test query_resources aggregate count (grade={valid_grade})", res_query_count)

    # 7. Test query_resources with group_by and count
    res_query_groupby_count = query_resources(group_by="practice", aggregate="count")
    print_result("Test query_resources group_by practice and aggregate count", res_query_groupby_count)

    # 8. Test query_resources with group_by and sum/avg on daily_rate_usd
    res_query_groupby_avg = query_resources(group_by="practice", aggregate="avg", aggregate_field="daily_rate_usd")
    print_result("Test query_resources group_by practice and aggregate avg of daily_rate_usd", res_query_groupby_avg)

    # 9. Test query_resources with filters, aggregate sum
    res_query_sum = query_resources(filters={"practice": valid_practice}, aggregate="sum", aggregate_field="monthly_billing_usd")
    print_result(f"Test query_resources aggregate sum (practice={valid_practice}, field=monthly_billing_usd)", res_query_sum)

    # 10. Test query_resources with filters returning empty results
    res_query_empty = query_resources(filters={"location_name": "NonExistentCity"})
    print_result("Test query_resources returning empty results", res_query_empty)

if __name__ == "__main__":
    main()
