"""Standalone script to test chatbot conversation turns end-to-end.
   Run with: python scripts/test_chat_turn.py"""
import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.chatbot.agents import ask

def test_question(q):
    print(f"USER: {q}")
    response = ask(q)
    print(f"AGENT:\n{response}")
    print("-" * 50)

def main():
    print("Starting End-to-End Chatbot Conversation Tests...\n")
    
    # Test 1: Name-based query
    test_question("Tell me about Aqib Chaudhry")
    
    # Test 2: ID-based query (Success)
    test_question("Can you look up the employee with ID 1001?")
    
    # Test 3: ID-based query (No match found / Error)
    test_question("Can you look up the employee with ID 999999?")
    
    # Test 4: Generic query (aggregation/grouping)
    test_question("What is the average daily rate in Software - TSF?")

if __name__ == "__main__":
    main()
