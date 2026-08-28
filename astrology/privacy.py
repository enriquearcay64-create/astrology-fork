"""Privacy boundaries for local-first operation.

No persistence is performed by the package.  These helpers expose the record
separation required if a commercial storage layer is added later.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict


def opaque_id(namespace: str, payload: Dict[str, Any], secret: bytes) -> str:
    """Create a stable pseudonymous id using an application-held secret.

    A plain hash is intentionally rejected because birth data has low entropy and
    can be recovered by dictionary enumeration.
    """
    if len(secret) < 32:
        raise ValueError("secret must contain at least 32 bytes")
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return namespace + "_" + hmac.new(secret, material, hashlib.sha256).hexdigest()[:20]
def record_boundaries() -> Dict[str, Dict[str, object]]:
    return {
        "implementation_status": {"storage": False, "encryption": False, "deletion_api": False, "note": "This package calculates in memory; a host application must enforce persistence controls."},
        "birth_record": {"contains": ["birth_date", "birth_time", "coordinates", "timezone"], "retention": "explicit host policy required"},
        "identity_record": {"contains": ["name", "contact"], "retention": "separate from birth_record"},
        "commercial_order": {"contains": ["order_reference", "report_type"], "retention": "separate from identity and birth records"},
        "manifestation_feedback": {"contains": ["user_reported_confirmation"], "retention": "opt-in only; never astrological evidence"},
        "report": {"contains": ["rendered_output", "methodology_version"], "retention": "user-controlled deletion"},
    }


def redact_for_logs(payload: Dict[str, Any]) -> Dict[str, Any]:
    sensitive = {"name", "birth_date", "birth_time", "local_datetime", "latitude", "longitude", "email", "place_label", "coordinates", "phone", "contact"}

    def sensitive_key(key: str) -> bool:
        normalized = key.casefold().replace("-", "_")
        parts = set(normalized.split("_"))
        return normalized in sensitive or bool(parts & sensitive) or any(token in normalized for token in ("email", "phone", "latitude", "longitude", "coordinate"))

    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: ("[redacted]" if sensitive_key(key) else redact(item)) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(redact(item) for item in value)
        return value

    return redact(payload)
