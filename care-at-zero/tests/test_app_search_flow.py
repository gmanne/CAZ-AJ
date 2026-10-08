"""Test the Find -> result card -> Detail flow with a mocked MCP client."""
import sys
import types

FAKE_SEARCH_RESULTS = [
    {
        "id": "test-1", "name": "Test Community Health Center", "facility_type": "Community Health Center",
        "cost_class": "Sliding Scale", "services": ["medical"], "address": "123 Main St, Raleigh, NC",
        "score": 78.5, "why_this_matches": ["Cost category: Sliding Scale", "0.1 mi away"],
        "next_date": None, "next_hours": None, "appointment_rule": "appointment_required",
        "source_name": "HRSA Health Care Service Delivery Sites",
    }
]
FAKE_DETAIL = {
    "id": "test-1", "name": "Test Community Health Center", "facility_type": "Community Health Center",
    "services": ["medical"], "cost_class": "Sliding Scale",
    "eligibility": "Federally required sliding fee scale based on income",
    "address": "123 Main St, Raleigh, NC", "phone": "919-555-0000", "website": "https://example.org",
    "documents_needed": "Contact clinic to confirm required documents",
    "appointment_rule": "appointment_required", "next_date": None, "next_hours": None,
    "source_name": "HRSA Health Care Service Delivery Sites", "source_url": "https://data.hrsa.gov/data/download",
    "last_checked": "2026-01-01T00:00:00+00:00",
    "score_breakdown": {
        "total": 78.5,
        "categories": {
            "cost_fit": {"score": 55, "weight_pct": 35, "points": 19.25, "reason": "Cost category: Sliding Scale"},
            "time_to_care": {"score": 75, "weight_pct": 25, "points": 18.75, "reason": "Ongoing permanent availability"},
            "service_match": {"score": 100, "weight_pct": 15, "points": 15.0, "reason": "Offers medical"},
            "eligibility_confidence": {"score": 85, "weight_pct": 10, "points": 8.5, "reason": "Eligibility criteria documented"},
            "distance": {"score": 100, "weight_pct": 10, "points": 10.0, "reason": "0.1 mi away"},
            "freshness": {"score": 100, "weight_pct": 5, "points": 5.0, "reason": "Source checked within the last week"},
        },
    },
}

def fake_call_tool(tool_name, arguments=None):
    if tool_name == "search_care":
        return FAKE_SEARCH_RESULTS
    if tool_name == "get_care_detail":
        return FAKE_DETAIL
    if tool_name == "get_referral_summary":
        return "CareAtZero Referral Summary\n============================\nTest Community Health Center"
    return {}

class FakeMCPUnavailableError(Exception):
    pass

fake_module = types.ModuleType("utils.mcp_client")
fake_module.call_tool = fake_call_tool
fake_module.MCPUnavailableError = FakeMCPUnavailableError
sys.modules["utils.mcp_client"] = fake_module

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("../app.py")
at.run(timeout=20)
assert not at.exception, f"Initial load raised: {at.exception}"

find_btn = [b for b in at.button if b.label == "Find"][0]
find_btn.click().run(timeout=20)
assert not at.exception

submit_btns = [b for b in at.button if "Find Care" in b.label]
print("Submit buttons found:", [b.label for b in submit_btns])
submit_btns[0].click().run(timeout=20)
print("\n=== AFTER SUBMITTING SEARCH ===")
print("Exceptions:", at.exception)
assert not at.exception, f"Search submit raised: {at.exception}"
print("Markdown snippets:", [m.value[:60] for m in at.markdown][:10])
assert any("Test Community Health Center" in m.value for m in at.markdown)

view_btns = [b for b in at.button if "View Details" in b.label]
print("View Details buttons:", len(view_btns))
view_btns[0].click().run(timeout=20)
print("\n=== AFTER CLICKING View Details ===")
print("Exceptions:", at.exception)
assert not at.exception, f"Detail view raised: {at.exception}"
titles = [t.value for t in at.title]
print("Titles:", titles)
assert any("Test Community Health Center" in t for t in titles)
print("Markdown (score breakdown check):", [m.value[:50] for m in at.markdown if "Score" in m.value or "%" in m.value][:5])

# Try saving from detail page
save_btns = [b for b in at.button if "Save" in b.label]
print("Save buttons on detail page:", [b.label for b in save_btns])
save_btns[0].click().run(timeout=20)
print("\n=== AFTER CLICKING Save ===")
print("Exceptions:", at.exception)
assert not at.exception, f"Save raised: {at.exception}"

print("\n=== ALL SEARCH-FLOW CHECKS PASSED ===")
