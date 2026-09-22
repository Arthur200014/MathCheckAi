






from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tools.ege13_reference import verify_ege13_reference
from src.tools.ege13_student import extract_ege13_student_evidence, verify_ege13_student_machine_spec
from src.tools.ege13_task_input import build_ege13_task_statement

CASES = ROOT / "evals" / "task_13" / "benchmark_cases.json"


def validate_case(case: dict) -> dict:
    statement = build_ege13_task_statement(case["task_equation"], case["interval"])
    reference = verify_ege13_reference({}, task_statement=statement)
    evidence = extract_ege13_student_evidence(case["manual_transcript"])
    math = None
    if reference.ok:
        math = verify_ege13_student_machine_spec(
            evidence.machine_spec(),
            task_statement=statement,
            reference_families=reference.verified_families,
            expected_roots=reference.expected_roots,
        )

    problems: list[str] = []
    if not reference.ok:
        problems.append("reference_failed:" + ";".join(reference.errors))
    if evidence.errors:
        problems.extend("student_parser:" + item for item in evidence.errors)
    if not evidence.part_a_present:
        problems.append("part_a_not_detected")

    score = int(case["expert_score"])
    if math is not None:
        if score == 2:
            if math.part_a_equivalent is not True:
                problems.append("expert_2_part_a_not_confirmed")
            if math.part_b_matches is not True:
                problems.append("expert_2_part_b_not_confirmed")
        elif score == 1:
                                                                             
                                                                                    
            if math.part_a_equivalent is not True:
                problems.append("expert_1_part_a_not_confirmed")
        elif score == 0:
                                                                                     
            if math.part_a_equivalent is True:
                problems.append("expert_0_part_a_unexpectedly_equivalent")

    return {
        "case_id": case["id"],
        "expert_score": score,
        "reference_ok": reference.ok,
        "part_a": None if math is None else math.part_a_equivalent,
        "part_b": None if math is None else math.part_b_matches,
        "families": len(evidence.general_solution_families),
        "roots": evidence.selected_roots,
        "parser_errors": evidence.errors,
        "problems": problems,
        "ok": not problems,
    }


def main() -> None:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if len(cases) != 12:
        raise SystemExit(f"FAIL: expected 12 eval cases, got {len(cases)}")

    rows = [validate_case(case) for case in cases]
    for row in rows:
        flag = "OK" if row["ok"] else "FAIL"
        print(
            f"{flag:4} {row['case_id']:8} expert={row['expert_score']} "
            f"A={row['part_a']} B={row['part_b']} families={row['families']} roots={row['roots']}"
        )
        for item in row["problems"]:
            print("     -", item)

    failed = [row for row in rows if not row["ok"]]
    print(f"\nRelease gate: {len(rows) - len(failed)}/{len(rows)} cases passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
# fix
