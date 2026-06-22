"""Evaluation Runner — batch tests all 20 prompts through the pipeline.

Runs each prompt, collects metrics, and produces a summary report.
Usage:
    python -m src.evaluation.runner --suite real
    python -m src.evaluation.runner --suite edge_cases
    python -m src.evaluation.runner --suite all
"""
import json
import time
import argparse
import traceback
from pathlib import Path
from uuid import uuid4

from src.config import SESSIONS_DIR
from src.pipeline.graph import pipeline


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompts(suite: str) -> list[dict]:
    """Load evaluation prompts by suite name."""
    prompts = []
    if suite in ("real", "all"):
        with open(PROMPTS_DIR / "real.json") as f:
            prompts.extend(json.load(f))
    if suite in ("edge_cases", "all"):
        with open(PROMPTS_DIR / "edge_cases.json") as f:
            prompts.extend(json.load(f))
    return prompts


def run_single(prompt_data: dict) -> dict:
    """Run a single prompt through the pipeline and collect metrics."""
    prompt_id = prompt_data["id"]
    prompt_text = prompt_data["prompt"]
    session_id = str(uuid4())

    initial_state = {
        "user_prompt": prompt_text,
        "mode": "generate",
        "session_id": session_id,
        "events": [],
        "stage_timings": {},
        "repair_attempts": {},
        "repair_history": [],
        "total_retries": 0,
        "cost_estimate": 0.0,
        "validation_errors": [],
        "test_results": [],
        "pipeline_failed": False,
    }

    start = time.time()
    result = {
        "id": prompt_id,
        "prompt": prompt_text[:100],
        "session_id": session_id,
        "success": False,
        "error": None,
        "total_time": 0,
        "stage_timings": {},
        "tables_created": 0,
        "endpoints_generated": 0,
        "validation_errors_critical": 0,
        "validation_errors_warning": 0,
        "repair_attempts": 0,
        "smoke_tests_passed": 0,
        "smoke_tests_total": 0,
        "entity_count": 0,
        "feature_count": 0,
        "confidence": "",
    }

    try:
        final_state = pipeline.invoke(initial_state)

        elapsed = round(time.time() - start, 2)
        result["total_time"] = elapsed
        result["stage_timings"] = final_state.get("stage_timings", {})
        result["success"] = True

        # Intent metrics
        intent = final_state.get("intent")
        if intent:
            result["entity_count"] = len(intent.entities)
            result["feature_count"] = len(intent.features)
            result["confidence"] = intent.confidence

        # Schema metrics
        db = final_state.get("db_schema")
        if db:
            result["tables_created"] = len(db.tables)

        api = final_state.get("api_schema")
        if api:
            result["endpoints_generated"] = len(api.endpoints)

        # Validation metrics
        errors = final_state.get("validation_errors", [])
        result["validation_errors_critical"] = len(
            [e for e in errors if e.get("severity") == "critical"]
        )
        result["validation_errors_warning"] = len(
            [e for e in errors if e.get("severity") == "warning"]
        )
        result["repair_attempts"] = final_state.get("total_retries", 0)

        # Smoke test metrics
        tests = final_state.get("test_results", [])
        result["smoke_tests_total"] = len(tests)
        result["smoke_tests_passed"] = len([t for t in tests if t.get("passed")])

        # Check entity coverage
        expected = prompt_data.get("expected_entities", [])
        if expected and db:
            actual_tables = {t.name for t in db.tables}
            covered = sum(1 for e in expected if e in actual_tables)
            result["entity_coverage"] = f"{covered}/{len(expected)}"

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        result["total_time"] = round(time.time() - start, 2)

    return result


def print_report(results: list[dict]) -> None:
    """Print a formatted evaluation report."""
    print("\n" + "=" * 80)
    print("  iWebify Evaluation Report")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r["success"])
    failed = total - passed

    print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
    print(f"  Success Rate: {(passed/total*100):.1f}%\n")

    # Per-prompt summary
    print(f"  {'ID':<20} {'Time':>6} {'Tables':>7} {'Endpoints':>10} {'Repairs':>8} {'Tests':>6} {'Status':>8}")
    print("  " + "-" * 75)

    for r in results:
        status = "✅" if r["success"] else "❌"
        tests = f"{r['smoke_tests_passed']}/{r['smoke_tests_total']}"
        print(
            f"  {r['id']:<20} {r['total_time']:>5.1f}s {r['tables_created']:>7} "
            f"{r['endpoints_generated']:>10} {r['repair_attempts']:>8} {tests:>6} {status:>8}"
        )

    # Aggregates
    if passed > 0:
        times = [r["total_time"] for r in results if r["success"]]
        tables = [r["tables_created"] for r in results if r["success"]]
        endpoints = [r["endpoints_generated"] for r in results if r["success"]]
        repairs = [r["repair_attempts"] for r in results if r["success"]]

        print("\n  Aggregate Metrics (successful runs):")
        print(f"    Avg time:       {sum(times)/len(times):.1f}s")
        print(f"    Avg tables:     {sum(tables)/len(tables):.1f}")
        print(f"    Avg endpoints:  {sum(endpoints)/len(endpoints):.1f}")
        print(f"    Avg repairs:    {sum(repairs)/len(repairs):.1f}")
        print(f"    Total repairs:  {sum(repairs)}")

    # Failed prompts
    if failed > 0:
        print("\n  Failed Prompts:")
        for r in results:
            if not r["success"]:
                print(f"    - {r['id']}: {r.get('error', 'Unknown error')}")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="iWebify Evaluation Runner")
    parser.add_argument(
        "--suite",
        choices=["real", "edge_cases", "all"],
        default="real",
        help="Which prompt suite to run",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        default=None,
        help="Run only specific prompt IDs",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save results to JSON file",
    )
    args = parser.parse_args()

    prompts = load_prompts(args.suite)

    if args.ids:
        prompts = [p for p in prompts if p["id"] in args.ids]

    if not prompts:
        print("No prompts to evaluate.")
        return

    print(f"\n🚀 Running {len(prompts)} evaluation prompts (suite: {args.suite})...\n")

    results = []
    for i, prompt_data in enumerate(prompts):
        print(f"  [{i+1}/{len(prompts)}] {prompt_data['id']}...", end=" ", flush=True)
        result = run_single(prompt_data)
        status = "✅" if result["success"] else "❌"
        print(f"{status} ({result['total_time']:.1f}s)")
        results.append(result)

    print_report(results)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
