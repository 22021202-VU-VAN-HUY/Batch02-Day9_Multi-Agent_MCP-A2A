"""Command-line demo for the Day08 Supervisor-Workers RAG system."""

from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from src.supervisor_workers import SupervisorAgent

load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query",
        nargs="?",
        default=(
            "Nghệ sĩ sử dụng ma tuý có thể chịu hình phạt nào "
            "theo pháp luật Việt Nam?"
        ),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = SupervisorAgent().run(
        args.query,
        top_k=args.top_k,
        use_reranking=not args.no_rerank,
    )

    if args.as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"Intent: {result.plan.intent}")
    print(f"Workers: {', '.join(result.plan.worker_names)}")
    print(
        f"Latency: {result.total_seconds:.2f}s "
        f"(retrieval: {result.retrieval_seconds:.2f}s)"
    )
    for report in result.worker_reports:
        print(
            f"- {report.name}: {report.status}, "
            f"{len(report.sources)} sources, confidence={report.confidence:.2f}"
        )
    print("\n" + result.answer)


if __name__ == "__main__":
    main()
