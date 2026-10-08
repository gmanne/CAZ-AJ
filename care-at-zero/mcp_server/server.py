"""
CareAtZero MCP Server

Exposes CareAtZero's care finder as tools any MCP-compatible AI
assistant (Claude Desktop, Claude Code, etc.) can call directly —
e.g. "Find free dental care near 27601 this week."

This reuses the SAME connectors and scoring engine as the Streamlit
app (app.py), so both stay in sync instead of drifting apart — no
sample/placeholder data, only real official sources (see
connectors/combined.py): HRSA (medical), SAMHSA (behavioral), and
NC DHHS Safety Net (dental + other facility types).

Requires Python 3.10+ (the official MCP SDK's minimum).

Run directly for a quick manual check:
    python mcp_server/server.py
Normally it's launched by an MCP client (like Claude Desktop) instead —
see README.md for the config snippet.
"""

import sys
from pathlib import Path

# Let this file import connectors/ and scoring/ from the project root
# regardless of which directory it's launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from connectors.combined import fetch_all_records
from connectors.zip_centroids import coords_for_zip
from scoring.care_access_score import score_record, WEIGHTS

mcp = FastMCP("careatzero")

# Search center for distance scoring. A real deployment would geocode
# the person's own ZIP — see README's note on location handling.
DEFAULT_LAT, DEFAULT_LON = 35.7796, -78.6382

_records_cache = None


def _records():
    """
    Lazily fetch and cache records for this server process — real
    HRSA (medical), SAMHSA (behavioral), and NC DHHS Safety Net
    (dental + other types). See connectors/combined.py.
    """
    global _records_cache
    if _records_cache is None:
        _records_cache = fetch_all_records(state_abbr="NC")
    return _records_cache


def _record_summary(record, breakdown):
    return {
        "id": record.id,
        "name": record.name,
        "facility_type": record.facility_type,
        "cost_class": record.cost_class,
        "services": record.services,
        "address": record.address,
        "score": breakdown.total,
        "why_this_matches": list(breakdown.reasons.values()),
        "next_date": record.next_date,
        "next_hours": record.next_hours,
        "appointment_rule": record.appointment_rule,
        "source_name": record.source_name,
    }


@mcp.tool()
def search_care(
    service: str,
    timing: str = "flexible",
    insurance_status: str = "uninsured",
    zip_code: str = "27601",
) -> list[dict]:
    """
    Search CareAtZero for free or low-cost care options, ranked by
    Care Access Score (cost fit, timing, service match, eligibility,
    distance, and data freshness).

    Args:
        service: one of 'medical', 'dental', 'vision', 'behavioral'
        timing: 'today', 'this_week', or 'flexible'
        insurance_status: 'uninsured', 'underinsured', or 'prefer_not_to_say'
        zip_code: a North Carolina ZIP code to search near. Resolved to
            real coordinates via the U.S. Census Bureau ZIP-centroid
            data (connectors/zip_centroids.py). Falls back to Raleigh
            if the ZIP isn't recognized as a valid NC ZIP.
    """
    try:
        coords = coords_for_zip(zip_code)
    except Exception:
        coords = None  # geocoding unavailable — fall back to the default center rather than crash
    lat, lon = coords if coords else (DEFAULT_LAT, DEFAULT_LON)

    matches = [r for r in _records() if service in r.services]
    scored = [
        (r, score_record(r, service, timing, insurance_status, lat, lon))
        for r in matches
    ]
    scored.sort(key=lambda pair: pair[1].total, reverse=True)
    return [_record_summary(r, b) for r, b in scored]


@mcp.tool()
def get_care_detail(
    record_id: str,
    service: str = "",
    timing: str = "flexible",
    insurance_status: str = "uninsured",
    zip_code: str = "27601",
) -> dict:
    """
    Get full details for one care option (documents needed, eligibility,
    hours, phone, website) by the id returned from search_care.

    If service is provided, also includes a score_breakdown (per-category
    weighted points, matching search_care's ranking, using the same real
    ZIP-resolved coordinates) for showing a "why this matches" detail view.
    """
    for r in _records():
        if r.id == record_id:
            detail = {
                "id": r.id,
                "name": r.name,
                "facility_type": r.facility_type,
                "services": r.services,
                "cost_class": r.cost_class,
                "eligibility": r.eligibility,
                "address": r.address,
                "phone": r.phone,
                "website": r.website,
                "documents_needed": r.documents_needed,
                "appointment_rule": r.appointment_rule,
                "next_date": r.next_date,
                "next_hours": r.next_hours,
                "source_name": r.source_name,
                "source_url": r.source_url,
                "last_checked": r.last_checked,
            }
            if service:
                try:
                    coords = coords_for_zip(zip_code)
                except Exception:
                    coords = None
                lat, lon = coords if coords else (DEFAULT_LAT, DEFAULT_LON)
                b = score_record(r, service, timing, insurance_status, lat, lon)
                detail["score_breakdown"] = {
                    "total": b.total,
                    "categories": {
                        key: {
                            "score": b.sub_scores[key],
                            "weight_pct": round(WEIGHTS[key] * 100),
                            "points": round(b.sub_scores[key] * WEIGHTS[key], 1),
                            "reason": b.reasons[key],
                        }
                        for key in WEIGHTS
                    },
                }
            return detail
    return {"error": f"No care option found with id '{record_id}'"}


@mcp.tool()
def list_upcoming_events() -> list[dict]:
    """
    List all upcoming free mobile/pop-up care events, soonest first.

    Currently always returns an empty list: none of the connected real
    sources (HRSA, SAMHSA, NC DHHS Safety Net) publish mobile/pop-up
    event schedules — they're all permanent sites. This tool is kept
    so a mobile-event connector can be added later without changing
    the tool interface.
    """
    events = [r for r in _records() if r.record_type == "event"]
    events.sort(key=lambda r: r.next_date or "9999-99-99")
    return [
        {
            "id": r.id,
            "name": r.name,
            "facility_type": r.facility_type,
            "services": r.services,
            "date": r.next_date,
            "hours": r.next_hours,
            "address": r.address,
            "cost_class": r.cost_class,
        }
        for r in events
    ]


@mcp.tool()
def get_referral_summary(record_id: str) -> str:
    """
    Get a plain-text referral summary for one care option — the same
    text a navigator or patient could print or text to themselves.
    """
    for r in _records():
        if r.id == record_id:
            lines = [
                "CareAtZero Referral Summary",
                "============================",
                r.name,
                f"{r.cost_class} · {', '.join(r.services)}",
                "",
                f"Address: {r.address}",
                f"Phone: {r.phone}",
                f"Website: {r.website}",
                "",
                f"Next available: {r.next_date} — {r.next_hours}" if r.next_date else f"Hours: {r.next_hours}",
                f"Documents to bring: {r.documents_needed}",
                f"Eligibility: {r.eligibility}",
                "",
                f"Source: {r.source_name} (last checked {r.last_checked})",
                "",
                "Generated by CareAtZero — not medical advice.",
            ]
            return "\n".join(lines)
    return f"No care option found with id '{record_id}'"


if __name__ == "__main__":
    mcp.run()
