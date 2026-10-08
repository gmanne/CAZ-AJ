"""
Combines all real data connectors into one record pool, so app.py, the
MCP server, and any future consumer all see the same combined data
instead of re-implementing this merge.

Real sources combined here:
    HRSAConnector        — medical (federal, live API)
    SAMHSAConnector      — behavioral health (federal, live API)
    NCSafetyNetConnector — dental + broader facility types (NC state data)

No sample/placeholder data is used in this live path. If a source is
unreachable (offline, firewall, that API is down), this logs a warning
and continues with whatever other sources succeeded — it never crashes
the app and never fabricates data to fill the gap.

Note: there is currently no real, freely-available public data source
found for vision care specifically, so vision searches will return real
results only once a suitable connector exists for that category — see
the README's "What's covered" section.
"""

import sys
from typing import List, Optional

from .base_connector import CareRecord, ConnectorUnavailableError
from .hrsa_connector import HRSAConnector
from .samhsa_connector import SAMHSAConnector
from .nc_safety_net_connector import NCSafetyNetConnector


def fetch_all_records(state_abbr: str = "NC", zip_prefix: Optional[str] = None) -> List[CareRecord]:
    """
    Real medical (HRSA), behavioral (SAMHSA), and dental/multi-type
    (NC DHHS Safety Net) records combined. Each source is fetched
    independently — one failing doesn't take down the others.
    """
    records: List[CareRecord] = []

    sources = [
        ("HRSA", lambda: HRSAConnector(state_abbr=state_abbr, zip_prefix=zip_prefix).fetch_records()),
        ("SAMHSA", lambda: SAMHSAConnector().fetch_records()),
        ("NC DHHS Safety Net", lambda: NCSafetyNetConnector(zip_prefix=zip_prefix).fetch_records()),
    ]

    for label, fetch in sources:
        try:
            records.extend(fetch())
        except ConnectorUnavailableError as e:
            print(f"[careatzero] {label} connector unavailable, skipping: {e}", file=sys.stderr)
        except Exception as e:
            # Defensive: an unexpected error in one source should never
            # take down the whole search.
            print(f"[careatzero] {label} connector raised an unexpected error, skipping: {e}", file=sys.stderr)

    return records
