"""Run this every time the Excel file has changes to pull in.
   python scripts\\run_sync.py"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.etl import sync_from_excel, sync_deals_from_excel

if __name__ == "__main__":
    sync_from_excel("data/Teknosys_Resource_Management_Tool_SAMPLE.xlsx")
    sync_deals_from_excel("data/Teknosys_Resource_Management_Tool_SAMPLE.xlsx")