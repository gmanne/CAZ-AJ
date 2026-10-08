"""
HRSA connector — REAL, LIVE data from a U.S. federal API.

Pulls active Health Care Service Delivery Sites (HRSA-funded community
health centers / FQHCs) from HRSA's public ArcGIS REST feature service.
No API key or registration required:
    https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/PrimaryHealthCareFacilities_FS/MapServer/0

This is real government open data — verified via a live query while
building this connector (see the query URL in _build_url below).

IMPORTANT — an honest limitation, not a bug:
This feed tells you WHERE a real, active HRSA health center is, but not
WHICH specific services (dental / vision / behavioral) each site offers
— that breakdown isn't part of this particular dataset. So every record
here is conservatively marked as offering only "medical" (comprehensive
primary care is a federal requirement for these sites), never a service
this feed doesn't actually confirm. Call the site directly to confirm
dental/vision/behavioral availability before referring someone.

Similarly, HRSA-funded health centers are required by federal law to
use a sliding fee scale based on income for the uninsured — never
assumed to be "Free" unless a specific site says so, matching the
"never mark Free unless the source says so" rule from the blueprint.
"""

from typing import List, Optional

import requests

from .base_connector import BaseConnector, CareRecord, ConnectorUnavailableError

QUERY_URL = (
    "https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/"
    "PrimaryHealthCareFacilities_FS/MapServer/0/query"
)

OUT_FIELDS = [
    "OBJECTID", "SITE_NM", "SITE_ADDRESS", "SITE_CITY", "SITE_STATE_ABBR",
    "SITE_ZIP_CD", "SITE_PHONE_NUM", "SITE_URL", "HCC_STATUS_DESC",
    "HCC_LOC_DESC", "HCC_LOC_SETTING_DESC", "HCC_TYP_DESC", "GRANTEE_NM",
]


class HRSAConnector(BaseConnector):
    """
    Real connector for HRSA-funded health center sites.

    state_abbr: two-letter state code to search (default 'NC' for the
        Research Triangle pilot). zip_prefix: optional 3-digit ZIP
        prefix to narrow further (e.g. '276' covers much of the
        Triangle). limit: max records to fetch per call.
    """

    source_type = "hrsa_federal_api"

    def __init__(self, state_abbr: str = "NC", zip_prefix: Optional[str] = None, limit: int = 50):
        self.state_abbr = state_abbr
        self.zip_prefix = zip_prefix
        self.limit = limit

    def _build_where_clause(self) -> str:
        clause = f"SITE_STATE_ABBR='{self.state_abbr}' AND HCC_STATUS_DESC='Active'"
        if self.zip_prefix:
            clause += f" AND SITE_ZIP_CD LIKE '{self.zip_prefix}%'"
        return clause

    def fetch_records(self) -> List[CareRecord]:
        params = {
            "where": self._build_where_clause(),
            "outFields": ",".join(OUT_FIELDS),
            "returnGeometry": "true",
            "f": "json",
            "resultRecordCount": self.limit,
        }
        try:
            resp = requests.get(QUERY_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            # Never silently fabricate data when the source can't be
            # reached — fail loudly instead (business rule 4.6).
            raise ConnectorUnavailableError(f"HRSA API unreachable: {e}") from e
        except ValueError as e:
            raise ConnectorUnavailableError(f"HRSA API returned unparseable data: {e}") from e

        if "error" in data:
            raise ConnectorUnavailableError(f"HRSA API error: {data['error']}")

        now = self.now_iso()
        records = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            geom = feature.get("geometry", {})
            lat, lon = geom.get("y"), geom.get("x")
            if lat is None or lon is None:
                continue  # skip records with no usable location

            site_type = "permanent"
            loc_desc = (attrs.get("HCC_LOC_DESC") or "").lower()
            if "mobile" in loc_desc:
                site_type = "mobile"
            elif "seasonal" in loc_desc or "temporary" in loc_desc:
                site_type = "pop_up"

            address_parts = [
                attrs.get("SITE_ADDRESS"), attrs.get("SITE_CITY"),
                attrs.get("SITE_STATE_ABBR"), attrs.get("SITE_ZIP_CD"),
            ]
            full_address = ", ".join(p for p in address_parts if p)

            # HRSA's own facility-type label, e.g. "Community Health
            # Center", "School-Based Health Center", "All Other Clinic
            # Types" — this IS in the feed, unlike per-service data.
            facility_type = attrs.get("HCC_LOC_SETTING_DESC") or attrs.get("HCC_TYP_DESC") or "Health Center"

            records.append(CareRecord(
                id=f"hrsa-{attrs.get('OBJECTID')}",
                name=attrs.get("SITE_NM") or "Unnamed HRSA Health Center",
                record_type="site",
                site_type=site_type,
                services=["medical"],  # see module docstring — the only service type this feed confirms
                cost_class="Sliding Scale",  # federally required sliding fee scale, not "Free"
                eligibility=(
                    "Federally required sliding fee scale based on income; "
                    "care provided regardless of insurance status or ability to pay"
                ),
                address=full_address,
                latitude=lat,
                longitude=lon,
                uninsured_accepted=True,
                appointment_rule="appointment_required",  # not in this feed — conservative default
                documents_needed="Contact clinic to confirm required documents",
                phone=attrs.get("SITE_PHONE_NUM") or "",
                website=attrs.get("SITE_URL") or "",
                source_name=f"HRSA Health Care Service Delivery Sites — {attrs.get('GRANTEE_NM', 'Unknown grantee')}",
                source_url="https://data.hrsa.gov/data/download",
                source_type=self.source_type,
                last_checked=now,
                next_hours=None,
                facility_type=facility_type,
            ))
        return records
