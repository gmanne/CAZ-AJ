"""
Care Access Engine — transparent scoring, no ML.

Implements the weights from blueprint section 4.5:
    Cost fit                          35%
    Time to care / upcoming avail.    25%
    Service match                     15%
    Eligibility confidence            10%
    Distance / travel burden          10%
    Information completeness/freshness 5%

Every sub-score is 0-100 and the weighted sum is also 0-100, so the
Access Score you show on a result card (e.g. "Score 94") is directly
this function's output. Each sub-score has a short reason string so the
UI can show "Why this matches" per UX principle 3.4, instead of an
unexplained number.
"""

from dataclasses import dataclass
from datetime import date, datetime
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, Optional, Tuple

from connectors.base_connector import CareRecord

WEIGHTS = {
    "cost_fit": 0.35,
    "time_to_care": 0.25,
    "service_match": 0.15,
    "eligibility_confidence": 0.10,
    "distance": 0.10,
    "freshness": 0.05,
}

COST_RANK = {"Free": 100, "Very Low Cost": 75, "Sliding Scale": 55, "Unknown": 20}


@dataclass
class ScoreBreakdown:
    total: float
    sub_scores: Dict[str, float]
    reasons: Dict[str, str]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lon points."""
    R = 3958.8  # Earth radius, miles
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _cost_fit(record: CareRecord) -> Tuple[float, str]:
    score = COST_RANK.get(record.cost_class, 20)
    return score, f"Cost category: {record.cost_class}"


def _time_to_care(record: CareRecord, timing_pref: str) -> Tuple[float, str]:
    """Rewards options that are available soon and match the user's urgency."""
    if record.next_date:
        try:
            days_out = (date.fromisoformat(record.next_date) - date.today()).days
        except ValueError:
            days_out = 999
        if days_out < 0:
            return 0, "Event has already passed"
        if days_out == 0:
            return 100, "Available today"
        if days_out <= 7:
            return 85, f"Upcoming in {days_out} day(s)"
        return max(30, 70 - days_out), f"Upcoming in {days_out} day(s)"

    # permanent site — score on how well its openness matches urgency
    if timing_pref == "today" and record.appointment_rule == "walk_in":
        return 90, "Walk-in available today"
    if timing_pref == "today":
        return 55, "Appointment required — may not be same-day"
    return 75, "Ongoing permanent availability"


def _service_match(record: CareRecord, requested_service: str) -> Tuple[float, str]:
    if requested_service.lower() in [s.lower() for s in record.services]:
        return 100, f"Offers {requested_service}"
    return 0, f"Does not list {requested_service}"


def _eligibility_confidence(record: CareRecord, insurance_status: Optional[str]) -> Tuple[float, str]:
    if not record.uninsured_accepted and insurance_status == "uninsured":
        return 10, "May not accept uninsured patients"
    if record.eligibility and len(record.eligibility) > 10:
        return 85, "Eligibility criteria documented"
    return 50, "Eligibility details limited"


def _distance_score(miles: Optional[float]) -> Tuple[float, str]:
    if miles is None:
        return 50, "Distance unknown"
    if miles <= 5:
        return 100, f"{miles:.1f} mi away"
    if miles <= 15:
        return 75, f"{miles:.1f} mi away"
    if miles <= 30:
        return 50, f"{miles:.1f} mi away"
    return 25, f"{miles:.1f} mi away"


def _freshness(record: CareRecord) -> Tuple[float, str]:
    try:
        checked = datetime.fromisoformat(record.last_checked)
        age_days = (datetime.now(checked.tzinfo) - checked).days
    except ValueError:
        return 40, "Freshness unknown"
    if age_days <= 7:
        return 100, "Source checked within the last week"
    if age_days <= 30:
        return 70, "Source checked within the last month"
    return 30, "Source data may be outdated"


def score_record(
    record: CareRecord,
    requested_service: str,
    timing_pref: str,
    insurance_status: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lon: Optional[float] = None,
) -> ScoreBreakdown:
    """
    Compute the Care Access Score for one record against one search.
    Returns 0 for service_match (and thus a low total) if the record
    doesn't offer the requested service — callers should still filter
    non-matches out before ranking per business rule 4.5.
    """
    cost, cost_reason = _cost_fit(record)
    time_s, time_reason = _time_to_care(record, timing_pref)
    service, service_reason = _service_match(record, requested_service)
    elig, elig_reason = _eligibility_confidence(record, insurance_status)

    miles = None
    if user_lat is not None and user_lon is not None:
        miles = haversine_miles(user_lat, user_lon, record.latitude, record.longitude)
    dist, dist_reason = _distance_score(miles)

    fresh, fresh_reason = _freshness(record)

    sub_scores = {
        "cost_fit": cost,
        "time_to_care": time_s,
        "service_match": service,
        "eligibility_confidence": elig,
        "distance": dist,
        "freshness": fresh,
    }
    reasons = {
        "cost_fit": cost_reason,
        "time_to_care": time_reason,
        "service_match": service_reason,
        "eligibility_confidence": elig_reason,
        "distance": dist_reason,
        "freshness": fresh_reason,
    }

    total = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return ScoreBreakdown(total=round(total, 1), sub_scores=sub_scores, reasons=reasons)
