"""End-to-end Stage 5 client with baseline and optimized latency modes."""

import argparse
import asyncio
import json

from dotenv import load_dotenv

load_dotenv()

from common.stage5_client import Stage5Result, ask_stage5

QUESTION = (
    "If a company breaks a contract and avoids taxes, "
    "what are the legal and regulatory consequences?"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["customer", "direct-law", "compare"],
        default="customer",
        help=(
            "customer: full baseline route; direct-law: optimized route; "
            "compare: run both sequentially"
        ),
    )
    parser.add_argument("--question", default=QUESTION)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def print_result(result: Stage5Result) -> None:
    print(f"Mode: {result.mode}")
    print(f"Trace ID: {result.trace_id}")
    print(f"Context ID: {result.context_id}")
    print(f"Route: {' -> '.join(result.route)}")
    print(
        "Latency: "
        f"{result.total_seconds:.2f}s total "
        f"({result.discovery_seconds:.2f}s discovery, "
        f"{result.request_seconds:.2f}s agent request)"
    )
    print("=" * 70)
    print(result.answer or "No text response received.")
    print("=" * 70)


async def main() -> None:
    args = parse_args()
    modes = ["customer", "direct-law"] if args.mode == "compare" else [args.mode]
    results: list[Stage5Result] = []

    for mode in modes:
        if not args.as_json:
            print(f"\nSending request with mode={mode}...")
        result = await ask_stage5(args.question, mode=mode)
        results.append(result)
        if not args.as_json:
            print_result(result)

    if args.as_json:
        payload: dict = {"results": [result.to_dict() for result in results]}
        if len(results) == 2 and results[0].total_seconds > 0:
            saved = results[0].total_seconds - results[1].total_seconds
            payload["comparison"] = {
                "seconds_saved": saved,
                "percent_reduction": saved / results[0].total_seconds * 100,
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif len(results) == 2:
        saved = results[0].total_seconds - results[1].total_seconds
        reduction = saved / results[0].total_seconds * 100
        print(
            "\nCOMPARISON: "
            f"{saved:.2f}s saved, {reduction:.1f}% lower latency "
            "(positive values mean direct-law was faster)."
        )


if __name__ == "__main__":
    asyncio.run(main())
