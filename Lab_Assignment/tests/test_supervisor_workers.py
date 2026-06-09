"""Tests for the Day08 Supervisor-Workers workflow."""

from __future__ import annotations

import unittest

from src.supervisor_workers import (
    SupervisorAgent,
    WorkerReport,
    _lightweight_retriever,
)


LEGAL_CHUNK = {
    "content": "Điều 249 quy định hình phạt đối với hành vi tàng trữ ma tuý.",
    "score": 0.95,
    "metadata": {
        "source": "Luat-73-2021-QH14.md",
        "path": "legal/Luat-73-2021-QH14.md",
        "type": "legal",
        "chunk_index": 1,
    },
}
NEWS_CHUNK = {
    "content": "Bài báo ghi nhận một nghệ sĩ bị bắt trong vụ án ma tuý.",
    "score": 0.85,
    "metadata": {
        "source": "article_01.md",
        "path": "news/article_01.md",
        "type": "news",
        "chunk_index": 2,
    },
}


def fake_retriever(query: str, **kwargs) -> list[dict]:
    return [LEGAL_CHUNK, NEWS_CHUNK]


def fake_generator(
    query: str,
    context: str,
    reports: list[WorkerReport],
    history: list[dict],
) -> str:
    return (
        f"answer:{query}|reports:{len(reports)}|"
        f"legal:{'Luat-73' in context}|news:{'article_01' in context}"
    )


class FailingNewsWorker:
    name = "news_research"
    role = "Worker intentionally fails during testing."

    def run(self, query: str, candidates: list[dict], top_k: int) -> WorkerReport:
        raise RuntimeError("news worker unavailable")


class SupervisorWorkersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor = SupervisorAgent(
            retriever=fake_retriever,
            answer_generator=fake_generator,
        )

    def test_registers_three_specialized_workers(self) -> None:
        self.assertEqual(
            set(self.supervisor.workers),
            {"legal_research", "news_research", "evidence_review"},
        )

    def test_routes_legal_question_to_two_workers(self) -> None:
        plan = self.supervisor.plan(
            "Luật quy định hình phạt tàng trữ trái phép chất ma tuý thế nào?"
        )

        self.assertEqual(plan.intent, "legal")
        self.assertEqual(
            plan.worker_names,
            ["legal_research", "evidence_review"],
        )

    def test_routes_news_question_to_two_workers(self) -> None:
        plan = self.supervisor.plan(
            "Nghệ sĩ nào bị bắt trong vụ việc gần đây?"
        )

        self.assertEqual(plan.intent, "news")
        self.assertEqual(
            plan.worker_names,
            ["news_research", "evidence_review"],
        )

    def test_mixed_question_runs_all_workers_and_aggregates_sources(self) -> None:
        result = self.supervisor.run(
            "Nghệ sĩ sử dụng ma tuý có thể chịu hình phạt nào?",
            top_k=5,
        )

        self.assertEqual(result.plan.intent, "mixed")
        self.assertEqual(len(result.worker_reports), 3)
        self.assertTrue(
            all(report.status == "completed" for report in result.worker_reports)
        )
        self.assertEqual(len(result.sources), 2)
        self.assertIn("reports:3", result.answer)
        self.assertIn("legal:True", result.answer)
        self.assertIn("news:True", result.answer)

    def test_worker_failure_is_isolated(self) -> None:
        supervisor = SupervisorAgent(
            retriever=fake_retriever,
            answer_generator=fake_generator,
        )
        supervisor.workers["news_research"] = FailingNewsWorker()

        result = supervisor.run(
            "Nghệ sĩ sử dụng ma tuý có thể chịu hình phạt nào?"
        )

        reports = {report.name: report for report in result.worker_reports}
        self.assertEqual(reports["news_research"].status, "failed")
        self.assertIn("unavailable", reports["news_research"].error)
        self.assertEqual(reports["legal_research"].status, "completed")
        self.assertEqual(reports["evidence_review"].status, "completed")
        self.assertTrue(result.answer)

    def test_rejects_empty_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            self.supervisor.run("  ")

    def test_lightweight_retriever_works_without_optional_models(self) -> None:
        results = _lightweight_retriever(
            "hình phạt tàng trữ ma tuý",
            top_k=3,
        )

        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 3)
        self.assertEqual(
            results[0]["metadata"]["retrieval"],
            "lightweight_fallback",
        )
        self.assertGreater(results[0]["score"], 0)


if __name__ == "__main__":
    unittest.main()
