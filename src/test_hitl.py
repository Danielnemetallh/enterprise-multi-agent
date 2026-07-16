"""
HITL test script: exercises human-in-the-loop with a cancellation ticket.
Runs agents step by step until the HITL stop.

Usage: python src/test_hitl.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.executive_agent import run_executive
from src.agents.triage_agent import classify_ticket
from src.tools.llm import extract_json, get_llm
from src.tools.policy import evaluate_policy
from src.tools.db_tools import query_open_tickets

tickets = [ticket for ticket in query_open_tickets() if ticket["category"] == "cancellation_request"]
if not tickets:
    print("No open cancellation tickets found.")
    sys.exit(1)

ticket = tickets[0]

print("\n" + "=" * 50)
print("HITL TEST: Process cancellation")
print("=" * 50)
print(f"\nTicket #{ticket['id']} ({ticket['ticket_id']})")
print(f"  Customer: {ticket['customer_name']} <{ticket['customer_email']}>")
print(f"  Subject: {ticket['subject']}")
print(f"  Description: {ticket['description'][:150]}...")

print("\n--- 1. Triage Agent ---")
classification = classify_ticket(ticket["subject"], ticket["description"])
print(f"  -> Classification: {classification}")

print("\n--- 2. Executive Agent ---")
collected = {"ticket": ticket}
action = run_executive(classification, collected)
print(f"  -> Proposal: {action['action_type']} | Discount: {action['discount_percent']}%")
print(f"  -> Subject: {action.get('subject', '?')}")
print(f"  -> Customer Draft: {action.get('customer_message', '?')}")

print("\n--- 3. HITL Check ---")
requires_approval = action.get("requires_approval", False)
print(f"  -> Requires approval? {'YES' if requires_approval else 'NO'}")


def show_proposal(proposal: dict) -> None:
    print("\n  Proposal:")
    print(f"  Action:   {proposal['action_type']}")
    print(f"  Discount: {proposal['discount_percent']}%")
    print(f"  Subject:  {proposal.get('subject', '?')}")
    print(f"  Draft:    {proposal.get('customer_message', '?')}")


if requires_approval:
    while True:
        print("\n" + "=" * 50)
        print("APPROVAL REQUIRED")
        print("=" * 50)
        show_proposal(action)

        response = input("  Approve action? (yes/no/alternative): ").strip().lower()

        if response in ("yes", "ja"):
            print("\n  APPROVED - action would be executed.")
            print(f"  Draft: {action.get('customer_message', '?')}")
            break

        if response in ("no", "nein"):
            print("\n  REJECTED - action would not be executed.")
            break

        if response in ("alternative", "eigen"):
            print("\n  Generating alternative proposal...")
            prompt = f"""The human reviewer rejected this proposed action:
{json.dumps(action, indent=2, ensure_ascii=False)}

Based on the SAME ticket details, suggest a DIFFERENT approach.

Respond with a JSON object:
{{
    "action_type": "offer_discount|send_apology|provide_information|process_cancellation",
    "discount_percent": <number 0-30>,
    "subject": "<short subject in English>",
    "customer_message": "<alternative response in English, max 2 sentences>",
    "business_reason": "<short internal reason>"
}}"""
            llm = get_llm(temperature=0.3)
            resp = llm.invoke(prompt)
            try:
                action = extract_json(resp.content)
                action.setdefault("action_type", "provide_information")
                action.setdefault("discount_percent", 0)
                action.setdefault("subject", "Alternative proposal")
                action.setdefault(
                    "customer_message",
                    "We have prepared an alternative response for you.",
                )
                action = evaluate_policy(action, classification, ticket)
                print("\n  -> New proposal created.")
            except (json.JSONDecodeError, IndexError) as exc:
                print(f"  Could not parse proposal: {exc}")
        else:
            print("  Please enter 'yes', 'no', or 'alternative'.")
else:
    print("\n  Auto-approved - action would be executed:")
    print(f"  Draft: {action.get('customer_message', '?')}")

print("\n" + "=" * 50)
print("Test complete.")
print("=" * 50)
