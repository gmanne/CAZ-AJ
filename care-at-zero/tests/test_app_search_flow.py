"""Test the Home search -> results -> clinic detail flow with a mocked MCP client.

The real MCP server is replaced by fake_call_tool, so this runs offline and
always returns the same clinic.

Run from the tests folder:  python test_app_search_flow.py
"""
import sys
import types

FAKE_SEARCH_RESULTS = [
    {
        "id": "test-1", "name": "Test Community Health Center", "facility_type": "Community Health Center",
        "cost_class": "Sliding Scale", "services": ["medical"], "address": "123 Main St, Raleigh, NC",
        "score": 78.5, "why_this_matches": ["Cost category: Sliding Scale", "0.1 mi away"],
        "next_date": None, "next_hours": None, "appointment_rule": "appointment_required",
        "source_name": "HRSA Health Care Service Delivery Sites", "phone": "919-555-0000",
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
REFERRAL = "CareAtZero Referral Summary\n============================\nTest Community Health Center"

calls = []


def fake_call_tool(tool_name, arguments=None):
    calls.append((tool_name, arguments))
    if tool_name == "search_care":
        return FAKE_SEARCH_RESULTS
    if tool_name == "get_care_detail":
        return FAKE_DETAIL
    if tool_name == "get_referral_summary":
        return REFERRAL
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


def page_text():
    return " ".join(m.value for m in at.markdown)


print("=== SEARCH FROM HOME ===")
submit = [b for b in at.button if b.label == "Find free care"][0]
submit.click().run(timeout=20)
assert not at.exception, f"Search submit raised: {at.exception}"
search_args = [a for name, a in calls if name == "search_care"][0]
assert search_args["service"] == "medical", "Medical is the default care type"
assert "Test Community Health Center" in page_text()
assert "SLIDING SCALE" in page_text(), "Cost label should be shown first on the card"
assert "Find care" in page_text(), "Searching from Home should open the Find tab"

print("=== OPEN CLINIC DETAIL ===")
[b for b in at.button if b.label == "Details"][0].click().run(timeout=20)
assert not at.exception, f"Detail view raised: {at.exception}"
assert "Test Community Health Center" in page_text()
assert "Care Access Score" in page_text()
assert not [b for b in at.button if "Save" in b.label], "Save was replaced by Download info"
assert any(c.value == REFERRAL for c in at.code), "Copy-this-info text should be on the detail screen"

print("=== BACK TO RESULTS ===")
[b for b in at.button if b.label == "Back"][0].click().run(timeout=20)
assert not at.exception, f"Back raised: {at.exception}"
assert "Find care" in page_text()

print("\n=== ALL SEARCH-FLOW CHECKS PASSED ===")
