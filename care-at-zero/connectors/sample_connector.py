"""
Sample connector — placeholder data for development and demos.

IMPORTANT: The records below are FICTIONAL placeholders (clearly marked
with "(Sample)" in the name) so the app has something to search/rank/
display while the real connectors are being built. Do not present this
data as real providers. Swap this connector out for a real one (e.g.
an HRSA Find a Health Center connector) before any public demo or
submission — see README for the connector checklist.

This is also the reference implementation for what a real connector
should look like: it just has to produce a list[CareRecord].
"""

from typing import List

from .base_connector import BaseConnector, CareRecord


class SampleConnector(BaseConnector):
    source_type = "sample_demo_data"

    def fetch_records(self) -> List[CareRecord]:
        now = self.now_iso()

        return [
            CareRecord(
                id="site-001",
                name="Triangle Community Health Center (Sample)",
                record_type="site",
                site_type="permanent",
                services=["medical", "dental"],
                cost_class="Sliding Scale",
                eligibility="Uninsured and underinsured adults; income-based fee scale",
                address="123 Main St, Raleigh, NC 27601",
                latitude=35.7796,
                longitude=-78.6382,
                uninsured_accepted=True,
                appointment_rule="appointment_required",
                documents_needed="Photo ID, proof of income if available",
                phone="(919) 555-0101",
                website="https://example.org/triangle-chc",
                source_name="Sample Demo Source",
                source_url="https://example.org/sources/demo",
                source_type=self.source_type,
                last_checked=now,
                next_hours="Mon-Fri 8am-5pm",
                facility_type="Community Health Center",
            ),
            CareRecord(
                id="site-002",
                name="Durham Free Dental Clinic (Sample)",
                record_type="site",
                site_type="permanent",
                services=["dental"],
                cost_class="Free",
                eligibility="Uninsured adults, income under 200% federal poverty line",
                address="456 Elm St, Durham, NC 27701",
                latitude=35.9940,
                longitude=-78.8986,
                uninsured_accepted=True,
                appointment_rule="walk_in",
                documents_needed="Photo ID",
                phone="(919) 555-0102",
                website="https://example.org/durham-free-dental",
                source_name="Sample Demo Source",
                source_url="https://example.org/sources/demo",
                source_type=self.source_type,
                last_checked=now,
                next_hours="Sat 9am-1pm",
                facility_type="Free Dental Clinic",
            ),
            CareRecord(
                id="event-001",
                name="Mobile Dental Clinic - Chapel Hill (Sample)",
                record_type="event",
                site_type="mobile",
                services=["dental"],
                cost_class="Free",
                eligibility="Open to all uninsured residents",
                address="Community Park, Chapel Hill, NC 27514",
                latitude=35.9132,
                longitude=-79.0558,
                uninsured_accepted=True,
                appointment_rule="walk_in",
                documents_needed="None required",
                phone="(919) 555-0103",
                website="https://example.org/mobile-dental",
                source_name="Sample Demo Source",
                source_url="https://example.org/sources/demo",
                source_type=self.source_type,
                last_checked=now,
                next_date="2026-09-20",
                facility_type="Mobile Dental Van",
            ),
            CareRecord(
                id="site-003",
                name="Wake Behavioral Health Access (Sample)",
                record_type="site",
                site_type="permanent",
                services=["behavioral"],
                cost_class="Very Low Cost",
                eligibility="Adults and adolescents; sliding scale for uninsured",
                address="789 Oak Ave, Raleigh, NC 27603",
                latitude=35.7721,
                longitude=-78.6386,
                uninsured_accepted=True,
                appointment_rule="appointment_required",
                documents_needed="Photo ID",
                phone="(919) 555-0104",
                website="https://example.org/wake-behavioral",
                source_name="Sample Demo Source",
                source_url="https://example.org/sources/demo",
                source_type=self.source_type,
                last_checked=now,
                next_hours="Mon-Thu 9am-6pm",
                facility_type="Community Mental Health Center",
            ),
            CareRecord(
                id="site-004",
                name="Cary Vision Care Center (Sample)",
                record_type="site",
                site_type="permanent",
                services=["vision"],
                cost_class="Sliding Scale",
                eligibility="Open to Wake County residents; discounted exams and glasses for uninsured",
                address="220 Kildaire Farm Rd, Cary, NC 27511",
                latitude=35.7915,
                longitude=-78.7811,
                uninsured_accepted=True,
                appointment_rule="appointment_required",
                documents_needed="Photo ID",
                phone="(919) 555-0110",
                website="https://example.org/cary-vision",
                source_name="Sample Demo Source",
                source_url="https://example.org/sources/demo",
                source_type=self.source_type,
                last_checked=now,
                next_hours="Tue-Fri 9am-4pm",
                facility_type="Vision Care Center",
            ),
        ]
