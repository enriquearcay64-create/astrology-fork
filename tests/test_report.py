from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.models import BirthData
from astrology.pipeline import analyse_birth_chart


def test_report_has_limits_and_traceable_content():
    result = analyse_birth_chart(
        BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333),
        report_depth="deep", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=30,
    )
    report = result["report"].casefold()
    technical = analyse_birth_chart(
        BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333),
        report_depth="technical", include_timing=False,
    )["report"].casefold()
    assert "predisposição simbólica" in report
    assert "não diagnostica" in report
    assert "evidence" in technical
    assert "## claims" in technical
    assert "bipolar" not in report
    assert "abandono" not in report
