"""Supervisor-Workers orchestration for the Day08 RAG pipeline.

The supervisor owns planning, retrieval, worker dispatch, failure isolation,
evidence aggregation, and final answer generation. Workers never call each
other and focus on one bounded responsibility.
"""

from __future__ import annotations

import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Callable, Protocol


Retriever = Callable[..., list[dict]]
AnswerGenerator = Callable[[str, str, list["WorkerReport"], list[dict]], str]


@dataclass(frozen=True)
class SupervisorPlan:
    """Routing decision produced before workers are dispatched."""

    intent: str
    worker_names: list[str]
    rationale: str


@dataclass(frozen=True)
class WorkerReport:
    """Structured output returned by one worker."""

    name: str
    role: str
    status: str
    findings: str
    sources: list[dict]
    confidence: float
    latency_seconds: float
    error: str = ""


@dataclass(frozen=True)
class SupervisorResult:
    """Final result returned to the CLI or Streamlit UI."""

    answer: str
    sources: list[dict]
    plan: SupervisorPlan
    worker_reports: list[WorkerReport]
    total_seconds: float
    retrieval_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class Worker(Protocol):
    """Contract implemented by all workers."""

    name: str
    role: str

    def run(self, query: str, candidates: list[dict], top_k: int) -> WorkerReport:
        """Process candidates and return a structured report."""


def _normalize_text(text: str) -> str:
    normalized = text.lower().replace("đ", "d")
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _source_name(chunk: dict) -> str:
    metadata = chunk.get("metadata", {}) or {}
    return str(
        metadata.get("source")
        or metadata.get("path")
        or chunk.get("source")
        or "unknown source"
    )


def _document_type(chunk: dict) -> str:
    metadata = chunk.get("metadata", {}) or {}
    explicit_type = str(
        metadata.get("type") or metadata.get("doc_type") or ""
    ).lower()
    if explicit_type in {"legal", "news"}:
        return explicit_type

    path = str(metadata.get("path") or _source_name(chunk)).replace("\\", "/").lower()
    if "/legal/" in f"/{path}" or path.startswith("legal/"):
        return "legal"
    if "/news/" in f"/{path}" or path.startswith("news/"):
        return "news"
    return "unknown"


def _copy_sources(chunks: list[dict], top_k: int) -> list[dict]:
    return [dict(chunk) for chunk in chunks[:top_k]]


def _confidence(chunks: list[dict]) -> float:
    if not chunks:
        return 0.0
    usable = sum(1 for chunk in chunks if chunk.get("content", "").strip())
    typed = sum(1 for chunk in chunks if _document_type(chunk) != "unknown")
    return round((usable + typed) / (2 * len(chunks)), 2)


def _findings(title: str, chunks: list[dict]) -> str:
    if not chunks:
        return f"{title}: không tìm thấy evidence phù hợp."

    lines = [title]
    for chunk in chunks:
        content = str(chunk.get("content", "")).strip().replace("\n", " ")
        preview = content[:240] + ("..." if len(content) > 240 else "")
        lines.append(f"- [{_source_name(chunk)}] {preview}")
    return "\n".join(lines)


class LegalResearchWorker:
    """Select and summarize evidence from statutes and legal documents."""

    name = "legal_research"
    role = "Tra cứu luật, nghị định, điều khoản và chế tài."

    def run(self, query: str, candidates: list[dict], top_k: int) -> WorkerReport:
        started = perf_counter()
        selected = [
            chunk for chunk in candidates if _document_type(chunk) == "legal"
        ][:top_k]
        return WorkerReport(
            name=self.name,
            role=self.role,
            status="completed",
            findings=_findings("Kết quả pháp lý", selected),
            sources=_copy_sources(selected, top_k),
            confidence=_confidence(selected),
            latency_seconds=perf_counter() - started,
        )


class NewsResearchWorker:
    """Select and summarize evidence from the news corpus."""

    name = "news_research"
    role = "Tra cứu sự kiện báo chí và đối chiếu thông tin vụ việc."

    def run(self, query: str, candidates: list[dict], top_k: int) -> WorkerReport:
        started = perf_counter()
        selected = [
            chunk for chunk in candidates if _document_type(chunk) == "news"
        ][:top_k]
        return WorkerReport(
            name=self.name,
            role=self.role,
            status="completed",
            findings=_findings("Kết quả báo chí", selected),
            sources=_copy_sources(selected, top_k),
            confidence=_confidence(selected),
            latency_seconds=perf_counter() - started,
        )


class EvidenceReviewWorker:
    """Review evidence quality and prepare a citation map."""

    name = "evidence_review"
    role = "Kiểm tra độ phủ nguồn, chất lượng evidence và citation."

    def run(self, query: str, candidates: list[dict], top_k: int) -> WorkerReport:
        started = perf_counter()
        selected = _copy_sources(candidates, top_k)
        legal_count = sum(
            1 for chunk in selected if _document_type(chunk) == "legal"
        )
        news_count = sum(
            1 for chunk in selected if _document_type(chunk) == "news"
        )
        unique_sources = list(dict.fromkeys(_source_name(chunk) for chunk in selected))

        if selected:
            findings = (
                "Đánh giá evidence\n"
                f"- Tổng chunks: {len(selected)}\n"
                f"- Nguồn pháp lý: {legal_count}\n"
                f"- Nguồn báo chí: {news_count}\n"
                f"- Nguồn duy nhất: {', '.join(unique_sources)}\n"
                "- Chỉ kết luận các nội dung có citation trong danh sách nguồn."
            )
        else:
            findings = (
                "Đánh giá evidence: không có nguồn đủ điều kiện; "
                "Supervisor phải từ chối suy đoán."
            )

        return WorkerReport(
            name=self.name,
            role=self.role,
            status="completed",
            findings=findings,
            sources=selected,
            confidence=_confidence(selected),
            latency_seconds=perf_counter() - started,
        )


class SupervisorAgent:
    """Plan and coordinate specialized RAG workers."""

    LEGAL_KEYWORDS = {
        "luat",
        "nghi dinh",
        "dieu",
        "hinh phat",
        "toi",
        "xu phat",
        "cai nghien",
        "quy dinh",
        "trach nhiem",
    }
    NEWS_KEYWORDS = {
        "nghe si",
        "dien vien",
        "ca si",
        "bao",
        "tin tuc",
        "bi bat",
        "vu viec",
        "duong tinh",
        "showbiz",
    }

    def __init__(
        self,
        retriever: Retriever | None = None,
        answer_generator: AnswerGenerator | None = None,
        workers: list[Worker] | None = None,
        max_workers: int = 3,
    ) -> None:
        self.retriever = retriever or _default_retriever
        self.answer_generator = answer_generator or _default_answer_generator
        worker_list = workers or [
            LegalResearchWorker(),
            NewsResearchWorker(),
            EvidenceReviewWorker(),
        ]
        self.workers = {worker.name: worker for worker in worker_list}
        self.max_workers = max(1, min(max_workers, len(self.workers)))

    def plan(self, query: str) -> SupervisorPlan:
        """Route a question to two or three workers based on its intent."""
        normalized = _normalize_text(query)
        has_legal = any(keyword in normalized for keyword in self.LEGAL_KEYWORDS)
        has_news = any(keyword in normalized for keyword in self.NEWS_KEYWORDS)

        if has_legal and not has_news:
            return SupervisorPlan(
                intent="legal",
                worker_names=["legal_research", "evidence_review"],
                rationale="Câu hỏi tập trung vào quy định và chế tài pháp luật.",
            )
        if has_news and not has_legal:
            return SupervisorPlan(
                intent="news",
                worker_names=["news_research", "evidence_review"],
                rationale="Câu hỏi tập trung vào sự kiện và thông tin báo chí.",
            )
        return SupervisorPlan(
            intent="mixed",
            worker_names=[
                "legal_research",
                "news_research",
                "evidence_review",
            ],
            rationale=(
                "Câu hỏi cần đối chiếu quy định pháp luật, sự kiện báo chí "
                "và chất lượng evidence."
            ),
        )

    def run(
        self,
        query: str,
        *,
        top_k: int = 5,
        score_threshold: float = 0.3,
        use_reranking: bool = True,
        history: list[dict] | None = None,
    ) -> SupervisorResult:
        """Execute retrieval, parallel workers, aggregation, and generation."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Query must not be empty.")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        total_started = perf_counter()
        plan = self.plan(normalized_query)

        retrieval_started = perf_counter()
        candidates = self.retriever(
            normalized_query,
            top_k=max(top_k * 2, 6),
            score_threshold=score_threshold,
            use_reranking=use_reranking,
        ) or []
        retrieval_seconds = perf_counter() - retrieval_started

        reports = self._dispatch(
            plan=plan,
            query=normalized_query,
            candidates=candidates,
            top_k=top_k,
        )
        sources = _merge_sources(reports, top_k=top_k)
        context = _format_supervisor_context(sources, reports)
        answer = self.answer_generator(
            normalized_query,
            context,
            reports,
            (history or [])[-6:],
        )

        return SupervisorResult(
            answer=answer,
            sources=sources,
            plan=plan,
            worker_reports=reports,
            total_seconds=perf_counter() - total_started,
            retrieval_seconds=retrieval_seconds,
        )

    def _dispatch(
        self,
        *,
        plan: SupervisorPlan,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[WorkerReport]:
        reports_by_name: dict[str, WorkerReport] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for worker_name in plan.worker_names:
                worker = self.workers.get(worker_name)
                if worker is None:
                    reports_by_name[worker_name] = WorkerReport(
                        name=worker_name,
                        role="Unknown worker",
                        status="failed",
                        findings="Worker không được đăng ký.",
                        sources=[],
                        confidence=0.0,
                        latency_seconds=0.0,
                        error=f"Unknown worker: {worker_name}",
                    )
                    continue
                future = executor.submit(worker.run, query, candidates, top_k)
                futures[future] = worker

            for future in as_completed(futures):
                worker = futures[future]
                try:
                    reports_by_name[worker.name] = future.result()
                except Exception as exc:
                    reports_by_name[worker.name] = WorkerReport(
                        name=worker.name,
                        role=worker.role,
                        status="failed",
                        findings=f"{worker.name} không hoàn thành.",
                        sources=[],
                        confidence=0.0,
                        latency_seconds=0.0,
                        error=str(exc),
                    )

        return [reports_by_name[name] for name in plan.worker_names]


def _merge_sources(reports: list[WorkerReport], top_k: int) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for report in reports:
        for source in report.sources:
            metadata = source.get("metadata", {}) or {}
            key = (
                _source_name(source),
                str(metadata.get("chunk_index", source.get("content", "")[:80])),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(dict(source))

    merged.sort(
        key=lambda item: float(item.get("score", 0.0) or 0.0),
        reverse=True,
    )
    return merged[:top_k]


def _format_supervisor_context(
    sources: list[dict],
    reports: list[WorkerReport],
) -> str:
    try:
        from .task10_generation import format_context, reorder_for_llm

        evidence_context = format_context(reorder_for_llm(sources))
    except Exception:
        evidence_context = "\n\n".join(
            f"[{_source_name(source)}]\n{source.get('content', '')}"
            for source in sources
        )

    worker_context = "\n\n".join(
        f"## {report.name} ({report.status})\n{report.findings}"
        for report in reports
    )
    return f"WORKER REPORTS\n{worker_context}\n\nEVIDENCE\n{evidence_context}".strip()


def _default_retriever(query: str, **kwargs) -> list[dict]:
    from .task9_retrieval_pipeline import retrieve

    try:
        return retrieve(query, **kwargs)
    except ModuleNotFoundError as exc:
        if exc.name not in {"sentence_transformers", "rank_bm25"}:
            raise
        return _lightweight_retriever(query, top_k=int(kwargs.get("top_k", 10)))


@lru_cache(maxsize=1)
def _load_lightweight_chunks() -> tuple[dict, ...]:
    """Load a dependency-free lexical corpus for local Supervisor demos."""
    standardized_dir = Path(__file__).resolve().parents[1] / "data" / "standardized"
    chunks: list[dict] = []
    for path in sorted(standardized_dir.rglob("*.md")):
        if path.name.startswith("."):
            continue
        relative_path = path.relative_to(standardized_dir)
        doc_type = relative_path.parts[0] if len(relative_path.parts) > 1 else "unknown"
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        sections = [
            section.strip()
            for section in re.split(r"\n\s*\n", text)
            if section.strip()
        ]
        chunk_index = 0
        for section in sections:
            windows = (
                [section]
                if len(section) <= 900
                else [
                    section[start : start + 900]
                    for start in range(0, len(section), 800)
                ]
            )
            for window in windows:
                chunks.append(
                    {
                        "content": window,
                        "score": 0.0,
                        "metadata": {
                            "source": path.name,
                            "path": str(relative_path).replace("\\", "/"),
                            "type": doc_type,
                            "chunk_index": chunk_index,
                            "retrieval": "lightweight_fallback",
                        },
                        "source": "hybrid-lite",
                    }
                )
                chunk_index += 1
    return tuple(chunks)


def _lightweight_retriever(query: str, top_k: int = 10) -> list[dict]:
    """Rank markdown chunks by normalized token overlap without extra packages."""
    query_tokens = set(re.findall(r"[a-z0-9]+", _normalize_text(query)))
    if not query_tokens or top_k <= 0:
        return []

    ranked: list[dict] = []
    for chunk in _load_lightweight_chunks():
        content = str(chunk.get("content", ""))
        content_tokens = re.findall(r"[a-z0-9]+", _normalize_text(content))
        if not content_tokens:
            continue
        content_token_set = set(content_tokens)
        overlap = query_tokens & content_token_set
        if not overlap:
            continue
        coverage = len(overlap) / len(query_tokens)
        frequency = sum(content_tokens.count(token) for token in overlap)
        score = coverage + min(frequency / max(len(content_tokens), 1), 0.25)
        item = dict(chunk)
        item["score"] = float(score)
        ranked.append(item)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]


def _default_answer_generator(
    query: str,
    context: str,
    reports: list[WorkerReport],
    history: list[dict],
) -> str:
    if not any(report.sources for report in reports):
        return "Tôi không thể xác minh thông tin này từ nguồn hiện có."

    try:
        from openai import OpenAI
        from .task10_generation import SYSTEM_PROMPT, TEMPERATURE, TOP_P

        mimo_key = os.getenv("MIMO_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if mimo_key:
            mimo_base_url = os.getenv(
                "MIMO_BASE_URL",
                "https://api.xiaomimimo.com/v1",
            ).strip()
            if mimo_base_url == "https://api.mimo.ai/v1":
                mimo_base_url = "https://api.xiaomimimo.com/v1"
            client = OpenAI(
                api_key=mimo_key,
                base_url=mimo_base_url,
            )
            model = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
        elif openai_key:
            client = OpenAI(api_key=openai_key)
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        else:
            return _fallback_supervisor_answer(reports)

        messages = [
            {
                "role": "system",
                "content": (
                    f"{SYSTEM_PROMPT}\n"
                    "Bạn là Supervisor. Hãy tổng hợp báo cáo của workers, "
                    "loại bỏ trùng lặp và nêu rõ khi evidence chưa đủ. "
                    "Trả lời tối đa 500 từ. Không tự suy đoán số điều, khoản "
                    "hoặc mức phạt nếu chúng không xuất hiện rõ trong evidence. "
                    "Citation phải dùng đúng tên source được cung cấp."
                ),
            }
        ]
        for message in history:
            role = message.get("role")
            content = message.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append(
            {
                "role": "user",
                "content": f"{context}\n\nQUESTION\n{query}",
            }
        )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_tokens=1536,
        )
        return str(response.choices[0].message.content or "").strip()
    except Exception as exc:
        fallback = _fallback_supervisor_answer(reports)
        return f"{fallback}\n\n[Ghi chú: LLM fallback do {exc}]"


def _fallback_supervisor_answer(reports: list[WorkerReport]) -> str:
    completed = [
        report.findings
        for report in reports
        if report.status == "completed" and report.sources
    ]
    if not completed:
        return "Tôi không thể xác minh thông tin này từ nguồn hiện có."
    return (
        "Supervisor đã tổng hợp evidence từ các workers:\n\n"
        + "\n\n".join(completed)
    )
