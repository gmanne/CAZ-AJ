"""
NC DHHS Safety Net connector — REAL, official North Carolina state data.

Downloads the NC Division of Public Health's published Safety Net Sites
list (dental clinics, health departments, FQHCs, free/charitable
clinics, school-based health centers, rural health clinics, etc.) and
normalizes it into CareRecords. No API key required — this is a public
CSV published by NC DHHS.

    https://files.nc.gov/dhhs/2024-10/SafetyNetList_2024_05_29.csv

IMPORTANT — honest limitations, not bugs:
- This is a periodically-updated static file, not a live queryable API.
  NC DHHS occasionally republishes it at a new URL (the filename/version
  changes) — if this connector starts returning zero records, check
  https://www.dph.ncdhhs.gov/programs/oral-health/services-individuals-and-families/safety-net-dental-clinics/safety-net-dental-clinic-locations
  for the current file link and update CSV_URL below.
- The file does not include latitude/longitude, so this connector
  resolves coordinates from ZIP code centroids (see zip_centroids.py)
  rather than the exact street address — accurate enough for a 10%-
  weighted distance score, not exact-address precision.
- The file does not break services down by medical/dental/vision/
  behavioral. This connector infers the service from the site's real
  "Facility Type" and name (e.g. "Dental Clinic" -> dental) — it never
  guesses a service the name/type doesn't indicate.
- The file does not include a cost tier. Cost class is inferred
  conservatively from well-documented facts about each facility
  category (e.g. HRSA-funded FQHCs are legally required to use a
  sliding fee scale) — never marked "Free" unless the facility's own
  name says so (e.g. "Free and Charitable Clinic", "A Storehouse For
  Jesus Dental Clinic" stays Sliding Scale since "Free" isn't in HRSA's
  or NCDHHS's own categorization of it).
"""

import csv
import io
from typing import List, Optional

import requests

from .base_connector import BaseConnector, CareRecord, ConnectorUnavailableError
from .zip_centroids import coords_for_zip, get_nc_zip_centroids

CSV_URL = "https://files.nc.gov/dhhs/2024-10/SafetyNetList_2024_05_29.csv?VersionId=RZ.SzREUlMozjDHiVvZ..WFWoArNAWHu"

# Facility types that are explicitly dental-only by name.
DENTAL_TYPES = {"Dental Clinic (stand alone)", "Dental Clinic (mobile)"}

# Facility types where "Free" is the category's own name — the clearest
# possible signal, matching "only mark Free when the source says so".
FREE_TYPES = {"Free and Charitable Clinic", "Free and Charitable Clinic (mobile)"}

SLIDING_SCALE_TYPES = {
    "Federally Qualified Health Center",
    "Federally Qualified Health Center/Health Department",
    "Health Department",
    "Federal CMS Certified Rural Health Clinic",
    "ORH Supported Rural Health Center",
}

# Hospitals aren't sliding-scale primary-care clinics — they're acute
# care facilities. Many do have financial-assistance/charity-care
# programs for the uninsured, but we don't have per-hospital data
# confirming that, so cost stays "Unknown" and eligibility says to ask
# about financial assistance specifically, rather than implying they're
# a walk-in free clinic like the rest of this list.
HOSPITAL_TYPES = {"Critical Access Hospital", "Small Rural Hospital"}

# School-Based Health Centers generally only serve students enrolled at
# that school, not the general public this app is built for. Excluded
# entirely rather than mislabeled or left to compete unfairly (on cost
# score) against real hospitals and clinics open to anyone.
SCHOOL_BASED_TYPES_PREFIX = "School Based Health Center"


def _infer_services(facility_type: str, name: str) -> List[str]:
    text = f"{facility_type} {name}".lower()
    if "dental" in text:
        return ["dental"]
    if "behavioral" in text or "mental health" in text:
        return ["behavioral"]
    return ["medical"]


def _infer_cost_class(facility_type: str) -> str:
    if facility_type in FREE_TYPES:
        return "Free"
    if facility_type in SLIDING_SCALE_TYPES or facility_type in DENTAL_TYPES:
        return "Sliding Scale"
    # Hospitals and clinics not otherwise categorized — genuinely
    # unknown from this feed rather than guessed.
    return "Unknown"


def _infer_site_type(facility_type: str) -> str:
    ft = facility_type.lower()
    if "mobile" in ft:
        return "mobile"
    return "permanent"


class NCSafetyNetConnector(BaseConnector):
    """Real connector for NC DHHS's published Safety Net Sites list."""

    source_type = "nc_dhhs_safety_net"

    def __init__(self, zip_prefix: Optional[str] = None):
        self.zip_prefix = zip_prefix

    def fetch_records(self) -> List[CareRecord]:
        try:
            resp = requests.get(CSV_URL, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectorUnavailableError(f"NC DHHS Safety Net list unreachable: {e}") from e

        try:
            centroids = get_nc_zip_centroids()
        except (requests.RequestException, Exception) as e:
            raise ConnectorUnavailableError(f"Could not load NC ZIP centroids for geocoding: {e}") from e

        now = self.now_iso()
        records: List[CareRecord] = []

        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            name = (row.get("Site Name") or "").strip()
            facility_type = (row.get("Facility Type") or "").strip()
            zip_code = (row.get("Zip_Code") or "").strip()[:5]
            if not name or not zip_code:
                continue
            if self.zip_prefix and not zip_code.startswith(self.zip_prefix):
                continue
            if facility_type.startswith(SCHOOL_BASED_TYPES_PREFIX):
                continue  # these generally only serve enrolled students, not the general public

            coords = coords_for_zip(zip_code, centroids)
            if coords is None:
                continue  # can't place it on the map reliably — skip rather than guess
            lat, lon = coords

            addr_parts = [
                row.get("Street_Address"), row.get("Street_Address_2"),
                row.get("City"), row.get("State"), zip_code,
            ]
            address = ", ".join(p.strip() for p in addr_parts if p and p.strip())

            cost_class = _infer_cost_class(facility_type)
            if facility_type in HOSPITAL_TYPES:
                eligibility = (
                    "Hospital — ask specifically about their financial assistance / "
                    "charity care program if uninsured; cost varies by service"
                )
            elif cost_class == "Free":
                eligibility = "Free care for qualifying patients; contact facility for eligibility details"
            elif cost_class == "Sliding Scale":
                eligibility = "Sliding-fee scale based on income; contact facility for eligibility details"
            else:
                eligibility = "Contact facility directly for cost and eligibility information"

            records.append(CareRecord(
                id=f"ncdhhs-{abs(hash((name, address))) % (10**10)}",
                name=name,
                record_type="site",
                site_type=_infer_site_type(facility_type),
                services=_infer_services(facility_type, name),
                cost_class=cost_class,
                eligibility=eligibility,
                address=address,
                latitude=lat,
                longitude=lon,
                uninsured_accepted=True,
                appointment_rule="appointment_required",  # not in feed — conservative default
                documents_needed="Contact facility to confirm required documents",
                phone=(row.get("phone_number1") or "").strip(),
                website="",  # not in this feed
                source_name=f"NC DHHS Safety Net List — {facility_type}" if facility_type else "NC DHHS Safety Net List",
                source_url="https://www.dph.ncdhhs.gov/programs/oral-health/services-individuals-and-families/safety-net-dental-clinics/safety-net-dental-clinic-locations",
                source_type=self.source_type,
                last_checked=now,
                next_hours=None,
                facility_type=facility_type or None,
            ))

        return records
