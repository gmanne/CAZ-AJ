"""
Base interface for source connectors.

Blueprint section 6.3: "Source Connectors - retrieve or refresh
provider/event records from supported public sources." Each real
connector (HRSA, a free-clinic network, a local nonprofit feed, etc.)
should subclass BaseConnector and implement fetch_records(). Keeping
every connector behind this same interface means the Normalization
Layer and Care Access Engine never need to know where a record came
from.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Optional


@dataclass
class CareRecord:
    """
    One normalized care option — a permanent site or a mobile/pop-up
    event, mapped to the common shape in blueprint section 6.4.
    """
    id: str
    name: str
    record_type: Literal["site", "event"]
    site_type: Literal["permanent", "mobile", "pop_up"]
    services: List[str]
    cost_class: Literal["Free", "Very Low Cost", "Sliding Scale", "Unknown"]
    eligibility: str
    address: str
    latitude: float
    longitude: float
    uninsured_accepted: bool
    appointment_rule: str
    documents_needed: str
    phone: str
    website: str
    source_name: str
    source_url: str
    source_type: str
    last_checked: str
    next_date: Optional[str] = None    # only set for events / time-limited care
    next_hours: Optional[str] = None   # only set for permanent sites with hours
    facility_type: Optional[str] = None  # e.g. "Community Health Center", "School-Based Health Center"


class BaseConnector(ABC):
    """Every source connector implements this interface."""

    source_type: str = "unknown"

    @abstractmethod
    def fetch_records(self) -> List[CareRecord]:
        """
        Return the current set of care records from this source.

        Implementations should:
        - never silently invent data when the source is unreachable
          (raise ConnectorUnavailableError instead — business rule 4.6)
        - only mark cost_class="Free" when the source explicitly says so
        - stamp last_checked with the actual fetch time
        """
        raise NotImplementedError

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ConnectorUnavailableError(Exception):
    """Raised when a source can't be reached. Never fabricate availability instead."""
    pass
