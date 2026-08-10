"""Run this first: python scripts\\run_load.py"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.etl import load_from_excel

if __name__ == "__main__":
    load_from_excel("data/Teknosys_Resource_Management_Tool_SAMPLE.xlsx")  # match your actual filename