"""Run the document golden set through the Guest/Child/Adult/Admin matrix.

Place this file beside ``run_document_pipeline_golden.py``, ``manifest.json``,
``docs/``, and ``truth/``. Python 3.9 compatible.

The runner never stores originals and always rejects derived actions. Each
role must use a separate authenticated test user token supplied through:

    AGENT_TEST_TOKEN_GUEST
    AGENT_TEST_TOKEN_CHILD
    AGENT_TEST_TOKEN_ADULT
    AGENT_TEST_TOKEN_ADMIN
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from run_document_pipeline_golden import (
    DEFAULT_ENDPOINT,
    AcceptanceFailure,
    _load_json,
    _load_manifest,
    _run_one,
    _selected_entries,
)


ROLES = ("Guest", "Child", "Adult", "Admin")

TOKEN_ENV = {
    "Guest": "AGENT_TEST_TOKEN_GUEST",
    "Child": "AGENT_TEST_TOKEN_CHILD",
    "Adult": "AGENT_TEST_TOKEN_ADULT",
    "Admin": "AGENT_TEST_TOKEN_ADMIN",
}

ROLE_DOMAINS = {
    "Guest": set(),
    "Child": {"food", "maintenance", "tasks"},
    "Adult": {"finance", "food", "maintenance", "tasks", "mixed"},
    "Admin": {"finance", "food", "maintenance", "tasks", "mixed"},
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the document golden set across the household roles."
    )
    parser.add_argument(
        "--golden-root",
        default=str(Path(__file__).resolve().parent),
        help="Directory containing manifest.json, docs/, and truth/.",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--roles",
        nargs="+",
        choices=ROLES,
        default=list(ROLES),
    )
    parser.add_argument("--ids", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--pause-seconds", type=float, default=0.0)
    parser.add_argument(
        "--report",
        default="document_pipeline_role_matrix_report.json",
    )
    return parser


def _tokens(roles: List[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    missing: List[str] = []
    for role in roles:
        env_name = TOKEN_ENV[role]
        token = str(os.environ.get(env_name) or "").strip()
        if token:
            values[role] = token
        else:
            missing.append(env_name)
    if missing:
        raise AcceptanceFailure(
            "Missing role-token environment variables: {0}".format(
                ", ".join(missing)
            )
        )
    return values


def _expected_domain(
    entry: Dict[str, Any],
    truth: Dict[str, Any],
) -> str:
    category = str(entry.get("category") or "").strip().casefold()
    doc_type = str(truth.get("doc_type") or "").strip().casefold()

    if category == "mixed_bundle" or doc_type == "mixed":
        # A mixed file includes a finance page, so the whole original remains
        # Adult-sensitive even if a maintenance keyword wins classification.
        return "mixed"
    if category == "handwritten_grocery" or doc_type == "grocery_list":
        return "food"
    if category in {"warranty_card", "manual"}:
        return "maintenance"
    if doc_type in {"warranty", "manual"}:
        return "maintenance"
    if category == "unreadable" or truth.get("expect_no_facts"):
        return "unknown"
    if category in {
        "printed_invoice",
        "printed_bill",
        "handwritten_bill",
    }:
        return "finance"
    if doc_type in {"invoice", "bill", "receipt"}:
        return "finance"
    return "unknown"


def _role_should_access(role: str, expected_domain: str) -> bool:
    if expected_domain == "unknown":
        return role in {"Adult", "Admin"}
    return expected_domain in ROLE_DOMAINS[role]


def _initial_http_status(record: Dict[str, Any]) -> Optional[int]:
    values = record.get("http_statuses") or []
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None


def _initial_step(record: Dict[str, Any]) -> Dict[str, Any]:
    steps = record.get("steps") or []
    if steps and isinstance(steps[0], dict):
        return steps[0]
    return {}


def _initial_reason(record: Dict[str, Any]) -> str:
    step = _initial_step(record)
    return str(
        step.get("reason")
        or step.get("response")
        or ""
    ).strip()


def _initial_classification_domain(record: Dict[str, Any]) -> str:
    classification = _initial_step(record).get("classification") or {}
    if not isinstance(classification, dict):
        return ""
    return str(classification.get("domain") or "").strip()


def _evaluate_role_result(
    role: str,
    expected_domain: str,
    record: Dict[str, Any],
) -> Tuple[bool, str]:
    should_access = _role_should_access(role, expected_domain)
    initial_status = _initial_http_status(record)
    accepted = initial_status == 200

    if should_access:
        if expected_domain == "unknown":
            if accepted or record.get("result") == "accepted_rejection":
                return True, "safe_unknown_handling"
        elif accepted and record.get("result") != "failed":
            if record.get("failures"):
                return False, "workflow_contract_failure"
            return True, "authorized"

        reason = _initial_reason(record).casefold()
        if initial_status == 409 and "exact duplicate" in reason:
            # Ingestion performs domain authorization before querying duplicate
            # fingerprints, so this response proves that RBAC admitted the
            # caller even though test state prevented a new review.
            return True, "authorized_duplicate"

        classification_domain = _initial_classification_domain(record)
        if (
            initial_status in {403, 422}
            and classification_domain in {"NeedsReview", "Unknown", ""}
            and "domain could not be established safely" in reason
        ):
            # This is a fail-closed OCR/classification-quality outcome, not an
            # RBAC denial of the golden truth domain. Keep it visible as a
            # warning without calling it an authorization regression.
            return True, "safe_unclassified_denial"

        return False, "authorized_role_was_rejected"

    if accepted:
        return False, "unauthorized_role_was_accepted"

    if initial_status in {401, 403, 404, 409, 422}:
        return True, "access_denied"

    return False, "unexpected_denial_response"


def main() -> int:
    args = _parser().parse_args()
    root = Path(args.golden_root).resolve()

    try:
        tokens = _tokens(list(args.roles))
        entries = _selected_entries(
            _load_manifest(root),
            args.ids,
            args.limit,
        )
    except (AcceptanceFailure, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report: Dict[str, Any] = {
        "endpoint": args.endpoint,
        "golden_root": str(root),
        "roles": list(args.roles),
        "store_originals": False,
        "approve_actions": False,
        "cases": [],
        "passed": 0,
        "failed": 0,
        "quality_warnings": 0,
    }

    total = len(entries) * len(args.roles)
    case_number = 0

    for entry in entries:
        doc_id = str(entry.get("doc_id") or "unknown")
        try:
            truth = _load_json(root / "truth" / (doc_id + ".json"))
            expected_domain = _expected_domain(entry, truth)
        except (AcceptanceFailure, OSError, ValueError) as exc:
            expected_domain = "unknown"
            truth = {}
            truth_error = str(exc)
        else:
            truth_error = None

        for role in args.roles:
            case_number += 1
            print(
                "[{0}/{1}] {2} as {3}".format(
                    case_number,
                    total,
                    doc_id,
                    role,
                )
            )

            if truth_error:
                record: Dict[str, Any] = {
                    "doc_id": doc_id,
                    "result": "failed",
                    "failures": [truth_error],
                    "steps": [],
                }
            else:
                try:
                    record = _run_one(
                        root=root,
                        entry=entry,
                        token=tokens[role],
                        endpoint=args.endpoint,
                        timeout=args.timeout,
                        store_originals=False,
                        approve_actions=False,
                    )
                except (AcceptanceFailure, OSError, ValueError) as exc:
                    record = {
                        "doc_id": doc_id,
                        "result": "failed",
                        "failures": [str(exc)],
                        "steps": [],
                    }

            passed, outcome = _evaluate_role_result(
                role,
                expected_domain,
                record,
            )
            case = {
                "doc_id": doc_id,
                "file": entry.get("file"),
                "category": entry.get("category"),
                "difficulty": entry.get("difficulty"),
                "expected_domain": expected_domain,
                "role": role,
                "expected_access": _role_should_access(
                    role,
                    expected_domain,
                ),
                "passed": passed,
                "outcome": outcome,
                "workflow": record,
            }
            if outcome == "safe_unclassified_denial":
                case["quality_warning"] = (
                    "The role was handled safely, but OCR/classification did "
                    "not establish the golden truth domain."
                )
                report["quality_warnings"] += 1
            report["cases"].append(case)

            if passed:
                report["passed"] += 1
                print("  OK: {0}".format(outcome))
            else:
                report["failed"] += 1
                print("  FAIL: {0}".format(outcome))

            if args.pause_seconds > 0:
                time.sleep(args.pause_seconds)

    report_path = Path(args.report).resolve()
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        "Completed: {0} passed, {1} failed. Report: {2}".format(
            report["passed"],
            report["failed"],
            report_path,
        )
    )
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
