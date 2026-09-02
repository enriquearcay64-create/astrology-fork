from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrology.models import LocalizationProfile
from astrology.pipeline import prepare_premium_handoff, validate_premium_author_bundle, validate_premium_narrative
import scripts.ux_editorial_audit as ux_audit
from scripts.ux_editorial_audit import generate, generate_premium_artifacts
from tests.test_v413_reader_contract import birth
from tests.v414_helpers import build_author_bundle_v14, reviewer_bundle_v14


def _approved_run(run_dir: Path, profile=None) -> None:
    handoff = prepare_premium_handoff(birth(), profile, include_timing=False)
    author, _ = build_author_bundle_v14(birth(), include_timing=False, profile=profile)
    provenance = validate_premium_author_bundle(birth(), author, profile, include_timing=False, prepared_handoff=handoff)
    assert provenance["approved"], provenance["verification_errors"]
    publication = validate_premium_narrative(reviewer_bundle_v14(author, provenance), provenance, birth(), profile, include_timing=False, prepared_handoff=handoff)
    assert publication["approved"], publication["verification_errors"]
    run_dir.mkdir()
    (run_dir / "05-provenance-guard.json").write_text(json.dumps(provenance), encoding="utf-8")
    (run_dir / "08-publication-guard.json").write_text(json.dumps(publication), encoding="utf-8")


def test_premium_artifact_audit_uses_approved_publication_and_canonical_parser(tmp_path):
    pt_run, en_run, output = tmp_path / "pt", tmp_path / "en", tmp_path / "out"
    _approved_run(pt_run)
    _approved_run(en_run, LocalizationProfile(preferred_language="en-US"))
    generate_premium_artifacts(output, "after", [pt_run, en_run])
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert set(metrics) == {"pt", "en"}
    assert len(metrics["pt"]["premium_canonical"]["canonical_domains"]) == 16
    assert metrics["pt"]["premium_canonical"]["opening_words"] > 0
    assert metrics["en"]["premium_canonical"]["integration_words"] > 0
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8"))["mode"] == "premium_artifacts"


def test_premium_artifact_audit_rejects_unapproved_or_incomplete_runs(tmp_path):
    run_dir = tmp_path / "bad"
    run_dir.mkdir()
    (run_dir / "05-provenance-guard.json").write_text(json.dumps({"approved": False}), encoding="utf-8")
    (run_dir / "08-publication-guard.json").write_text(json.dumps({"approved": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        generate_premium_artifacts(tmp_path / "out", "after", [run_dir])
    with pytest.raises(ValueError, match="requires 05"):
        generate_premium_artifacts(tmp_path / "out", "after", [tmp_path / "missing"])


def test_legacy_fixture_mode_remains_available(tmp_path):
    generate(tmp_path / "fixtures", "after", __import__("scripts.ux_editorial_audit", fromlist=["AS_OF"]).AS_OF, 366, ["A"])
    assert (tmp_path / "fixtures" / "A" / "deep.md").is_file()


def test_premium_domain_metrics_uses_mathematical_median_for_even_domain_count(monkeypatch):
    counts = [1, 3, 9, 11]
    domains = [{"id": f"domain_{index}", "availability": "available"} for index in range(len(counts))]
    sections = {
        "opening": {"prose": []},
        "integration": {"prose": []},
        **{
            domain["id"]: {"prose": [{"text": " ".join(["word"] * count)}]}
            for domain, count in zip(domains, counts)
        },
    }
    monkeypatch.setattr(ux_audit, "_parse_premium_narrative", lambda _report, _manifest: {"errors": [], "sections": sections})

    metrics = ux_audit._premium_domain_metrics("approved report", {"domains": domains})

    assert metrics["available_domain_word_median"] == 6.0
    assert metrics["available_domain_largest_to_median_ratio"] == 1.833


def test_premium_acceptance_documentation_has_no_hidden_quota_or_semantic_authority_leak():
    skill_root = Path(__file__).resolve().parents[1]
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    report_design = (skill_root / "references" / "report-design.md").read_text(encoding="utf-8")
    qa = (skill_root / "references" / "qa.md").read_text(encoding="utf-8")

    assert "Use no máximo um exemplo" not in report_design
    assert "Três exemplos totais" not in report_design
    assert "Premium não tem quota de exemplos" in report_design
    assert "não há quantidade-alvo" in report_design
    assert "reader_introduction` locale-bound materializado no handoff preparado" in skill
    assert "reader_introduction` locale-bound materializado no handoff preparado" in report_design
    assert "`reasoning_packet` é sua única autoridade para significado astrológico" in skill
    assert "Campos top-level do handoff servem somente a workflow, apresentação e proveniência" in skill
    assert "nunca introduzem significado astrológico" in skill
    assert "O alvo permanece aproximadamente `4`" in qa
    assert "`3–5` é somente tolerância de aceitação" in qa
    assert "nunca vira instrução numérica para o Author nem gate automático" in qa
