"""Installed command-line interface for the local astrology engine."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, Optional

from .engine import calculate_chart
from .models import BirthData, LocalizationProfile
from .pipeline import analyse_birth_chart, consult, prepare_premium_handoff, validate_premium_author_bundle, validate_premium_narrative, validate_premium_syntheses
from .timing import solar_return


def _load(path: str) -> Dict[str, object]:
    from .benchmark_integrity import load_json
    return load_json(path)


def _birth(data: Dict[str, object]) -> BirthData:
    allowed = {"local_datetime", "timezone_name", "latitude", "longitude", "place_label", "utc_offset_override_minutes", "time_uncertainty_minutes", "calendar", "source", "dst_fold", "birth_time_known", "sensitivity_test_minutes"}
    unknown = sorted(set(data) - allowed - {"localization_profile", "solar_return_location"})
    if unknown:
        raise ValueError("unknown input fields: " + ", ".join(unknown))
    return BirthData(**{key: value for key, value in data.items() if key in allowed})


def _profile(data: Dict[str, object]) -> Optional[LocalizationProfile]:
    profile = data.get("localization_profile")
    if not profile:
        return None
    if not isinstance(profile, dict):
        raise ValueError("localization_profile must be an object")
    allowed = {"preferred_language", "current_country", "cultural_context", "region", "source", "localization_level"}
    unknown = sorted(set(profile) - allowed)
    if unknown:
        raise ValueError("unknown localization_profile fields: " + ", ".join(unknown))
    return LocalizationProfile(**profile)


from .premium_workflow import prepared_timing_parameters as _prepared_timing_parameters, build_author_selection_prompt, prepare_author_from_selection, validate_frozen_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic astrology calculation and structured reading.")
    parser.add_argument("input", help="JSON with birth data and optional localization_profile")
    parser.add_argument("--depth", choices=("executive", "deep", "technical"), default=None)
    parser.add_argument("--no-timing", action="store_true")
    parser.add_argument("--horizon-days", type=int, default=366)
    parser.add_argument("--question", help="Run constrained consultation mode")
    parser.add_argument("--solar-return-year", type=int)
    parser.add_argument("--solar-return-location-policy", choices=("birth_place", "habitual_residence", "actual_physical_location"), default="birth_place")
    parser.add_argument("--as-of", help="UTC ISO timestamp for reproducible timing")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--premium-stage", choices=("prepare", "prepare-selection", "validate-selection", "prepare-author", "validate-synthesis", "validate-narrative", "prepare-run", "run-captured", "evaluate-captured", "reveal-captured", "replay-captured"), help="Manual Sol High handoff; does not call an external model")
    parser.add_argument("--premium-synthesis", help="AuthorBundle JSON, or a raw ReasonedSynthesis list for synthesis-only debugging")
    parser.add_argument("--premium-narrative", help="ReviewerBundle JSON with final_report and paragraph source mapping")
    parser.add_argument("--premium-handoff", help="Original deterministic handoff JSON that authoritatively binds a premium lineage")
    parser.add_argument("--premium-selection", help="Author-owned SelectionPlan JSON for the frozen handoff")
    parser.add_argument("--run-dir", help="Captured execution directory")
    parser.add_argument("--model", help="Explicit configured Gemini API model identifier")
    parser.add_argument("--thinking-level", choices=("low", "medium", "high"), default=None, help="Explicit Gemini thinking level")
    parser.add_argument("--candidate-model", help="Candidate model identifier for pre-frozen benchmark spec")
    parser.add_argument("--evaluator-model", help="Evaluator model identifier for pre-frozen benchmark spec")
    parser.add_argument("--evaluator-thinking-level", choices=("low", "medium", "high"), default=None, help="Explicit Gemini thinking level for evaluator")
    parser.add_argument("--benchmark-spec", help="Path to pre-frozen benchmark specification JSON")
    parser.add_argument("--champion-descriptor", help="Champion compatibility descriptor JSON")
    parser.add_argument("--champion-run", help="Captured champion run directory")
    parser.add_argument("--audit-record", help="Independent benchmark-ready code audit JSON")
    parser.add_argument("--champion-report", help="Comparison report, supplied only to the blind evaluator")
    parser.add_argument("--rubric", help="Frozen evaluation rubric JSON")
    args = parser.parse_args()
    try:
        data = _load(args.input)
        birth = _birth(data)
        profile = _profile(data)
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else None
        if as_of is not None and as_of.tzinfo is None:
            raise ValueError("--as-of must include a UTC offset")
        if args.premium_stage in {"prepare-run", "run-captured", "evaluate-captured", "reveal-captured", "replay-captured"}:
            from pathlib import Path
            from .isolated_execution import RunStore, GeminiTransport
            from .live_premium import prepare_run, continue_run, verify_captured_derivation, finalize_trace
            from .blind_execution import commit_blind, evaluate_blind, reveal_blind
            if not args.run_dir:
                raise ValueError("--run-dir is required")
            if args.premium_stage == "prepare-run":
                if not args.audit_record:
                    raise ValueError("--audit-record is required before live generation")
                bench_spec = None
                if args.benchmark_spec:
                    bench_spec = _load(args.benchmark_spec)
                elif args.rubric and (args.champion_report or args.champion_descriptor or args.champion_run):
                    from .benchmark_spec import create_benchmark_spec, derive_champion_from_run
                    from .isolated_execution import git_commit
                    repo = Path(__file__).resolve().parents[1]
                    handoff = prepare_premium_handoff(birth, profile, as_of=as_of, horizon_days=args.horizon_days, include_timing=not args.no_timing)
                    if args.champion_run:
                        champ_desc, champ_bytes = derive_champion_from_run(args.champion_run, repo)
                    else:
                        champ_desc = _load(args.champion_descriptor) if args.champion_descriptor else {}
                        champ_bytes = Path(args.champion_report).read_bytes() if args.champion_report else b""
                    cand_model = args.candidate_model or args.model or "gemini-3.8-flash"
                    cand_tl = args.thinking_level or "high"
                    eval_model = args.evaluator_model or cand_model
                    eval_tl = args.evaluator_thinking_level or "high"
                    bench_spec = create_benchmark_spec(
                        birth, profile, handoff, _load(args.rubric), champ_desc,
                        champ_bytes, cand_model, cand_tl, eval_model,
                        repo, git_commit(repo),
                        evaluator_thinking_level=eval_tl,
                    )
                store = prepare_run(args.run_dir, Path(__file__).resolve().parents[1], birth, profile,
                    as_of=as_of, horizon_days=args.horizon_days, include_timing=not args.no_timing,
                    audit_record=_load(args.audit_record), benchmark_spec=bench_spec)
                result = {"stage": "prepared", "run_dir": str(store.root), "benchmark_spec_frozen": bench_spec is not None}
            else:
                store = RunStore(args.run_dir)
                validate_frozen_inputs(_load(str(store.path("01-handoff.json"))), birth, profile)
                if args.premium_stage == "run-captured":
                    transport = GeminiTransport(args.model, thinking_level=args.thinking_level)
                    result = continue_run(store, transport)
                elif args.premium_stage == "evaluate-captured":
                    if not store.path("assignment_commitment.json").exists():
                        if not args.rubric or (not args.champion_report and not args.champion_run):
                            raise ValueError("--rubric and (--champion-report or --champion-run) are required before blind commitment")
                        if args.champion_run:
                            from .benchmark_spec import derive_champion_from_run
                            champ_desc, champ_bytes = derive_champion_from_run(args.champion_run, Path(__file__).resolve().parents[1])
                        else:
                            champ_desc = _load(args.champion_descriptor) if args.champion_descriptor else None
                            champ_bytes = Path(args.champion_report).read_bytes()
                        commit_blind(store, champ_bytes, _load(args.rubric), champion_descriptor=champ_desc)
                    eval_transport = GeminiTransport(args.model, thinking_level=args.thinking_level)
                    result = evaluate_blind(store, eval_transport)
                elif args.premium_stage == "reveal-captured":
                    result = {"reveal": reveal_blind(store), "manifest": finalize_trace(store)}
                else:
                    result = {"deterministic_replay_approved": verify_captured_derivation(store), "run_dir": str(store.root)}
        elif args.premium_stage == "prepare":
            result = prepare_premium_handoff(birth, profile, args.depth or "deep", not args.no_timing, as_of, args.horizon_days)
        elif args.premium_stage == "prepare-selection":
            result = prepare_premium_handoff(birth, profile, args.depth or "deep", not args.no_timing, as_of, args.horizon_days)
            result["author_selection_prompt"] = build_author_selection_prompt(result)
        elif args.premium_stage in {"validate-selection", "prepare-author"}:
            if not args.premium_handoff or not args.premium_selection:
                raise ValueError("--premium-handoff and --premium-selection are required")
            handoff = _load(args.premium_handoff)
            validate_frozen_inputs(handoff, birth, profile)
            selection = _load(args.premium_selection)
            result = prepare_author_from_selection(handoff, selection, handoff["reader_domain_manifest"].get("locale", "pt-BR"))
            if args.premium_stage == "validate-selection":
                result = {"stage": "selection_validated", "approved": True, "packet_id": handoff["packet_id"]}
        elif args.premium_stage == "validate-synthesis":
            if not args.premium_synthesis:
                raise ValueError("--premium-synthesis is required with --premium-stage validate-synthesis")
            payload = _load(args.premium_synthesis)
            if isinstance(payload, dict) and "reasoned_syntheses" in payload:
                if not args.premium_handoff:
                    raise ValueError("--premium-handoff is required when validating an AuthorBundle")
                handoff = _load(args.premium_handoff)
                prepared_as_of, prepared_horizon, prepared_timing = _prepared_timing_parameters(handoff)
                result = validate_premium_author_bundle(
                    birth, payload, profile, prepared_as_of, prepared_horizon, prepared_timing,
                    prepared_handoff=handoff,
                )
            else:
                items = payload.get("reasoned_synthesis", payload) if isinstance(payload, dict) else payload
                if not isinstance(items, list):
                    raise ValueError("premium synthesis must be a JSON list or an object with reasoned_synthesis")
                result = validate_premium_syntheses(birth, items, profile, as_of, args.horizon_days, not args.no_timing)
        elif args.premium_stage == "validate-narrative":
            if not args.premium_synthesis or not args.premium_narrative or not args.premium_handoff:
                raise ValueError("--premium-handoff, --premium-synthesis and --premium-narrative are required with --premium-stage validate-narrative")
            author_bundle = _load(args.premium_synthesis)
            if not isinstance(author_bundle, dict) or "reasoned_syntheses" not in author_bundle:
                raise ValueError("--premium-synthesis must be an AuthorBundle JSON for narrative publication")
            handoff = _load(args.premium_handoff)
            prepared_as_of, prepared_horizon, prepared_timing = _prepared_timing_parameters(handoff)
            provenance = validate_premium_author_bundle(
                birth, author_bundle, profile, prepared_as_of, prepared_horizon, prepared_timing,
                prepared_handoff=handoff,
            )
            result = validate_premium_narrative(
                _load(args.premium_narrative), provenance, birth, profile,
                prepared_as_of, prepared_horizon, prepared_timing,
                prepared_handoff=handoff,
            )
        elif args.solar_return_year:
            declared = data.get("solar_return_location")
            location = (birth.latitude, birth.longitude) if args.solar_return_location_policy == "birth_place" else (float(declared["latitude"]), float(declared["longitude"])) if isinstance(declared, dict) else None
            result = solar_return(calculate_chart(birth), args.solar_return_year, args.solar_return_location_policy, location)
        elif args.question:
            result = consult(birth, args.question, profile, as_of)
        else:
            result = analyse_birth_chart(birth, profile, args.depth or "executive", not args.no_timing, as_of, args.horizon_days)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        json.dump({"error": type(error).__name__, "message": str(error)}, sys.stderr, ensure_ascii=False)
        print(file=sys.stderr)
        return 2
    if args.format == "report" and isinstance(result, dict) and "report" in result:
        print(result["report"])
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0
