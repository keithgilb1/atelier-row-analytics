"""The analyst agent: a tool-use loop over the governed semantic layer, with every answer logged."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from atelier.agent.tools import TOOL_DEFINITIONS, AnswerSubmission, Toolbox, ToolCallRecord
from atelier.paths import AGENT_LOG_DIR

DEFAULT_MODEL = os.environ.get("ATELIER_AGENT_MODEL", "claude-opus-5-5")
MAX_TURNS = 12

SYSTEM_PROMPT = """\
You are the analytics assistant for Atelier Row, a resale boutique for luxury handbags with stores in
New York, Los Angeles and Miami and an online channel that ships from New York stock.

You answer business questions from the company's governed data. Rules:

- Certified metrics come first. For anything about sales, comp sales, margin, selling price, days to
  sell, inventory, aged stock or sell-through, call list_metrics and answer with query_metrics. Those
  numbers match every dashboard because they come from one definition. Never rebuild a certified
  metric in run_sql, even if you think you know the formula.
- "Comp", "comps" or "like-for-like" growth means comp_store_sales_growth (boutiques only) unless the
  person asks to include online, then comp_sales_growth. Comps only count days with a matching day last
  year, so a year-to-date comp is already like-for-like.
- The fiscal year runs July to June and is named for the year it ends: FY2026 is Jul 2025 to Jun 2026.
  FY2027 is in progress; the data runs to 2026-11-21. Group by metric_time__fiscal_year for fiscal years.
- Use run_sql only for questions no certified metric covers, and say the figure is ad hoc.
- Customer personal data (names, contact details) is not available. Say so if asked.
- If the data cannot answer the question, say that plainly instead of guessing.
- Finish by calling submit_answer once. Keep the answer short: lead with the number, then one or two
  sentences of context, and name the metric you used.
"""


class MessagesClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


@dataclass
class AgentResult:
    run_id: str
    question: str
    model: str
    answer: AnswerSubmission | None
    tool_calls: list[ToolCallRecord]
    turns: int
    latency_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    error: str | None = None
    paths: list[str] = field(default_factory=list)

    def to_log(self) -> dict:
        d = asdict(self)
        d["logged_at"] = datetime.now(timezone.utc).isoformat()
        return d


def _anthropic_messages() -> MessagesClient:
    import anthropic

    client = anthropic.Anthropic()

    class _Client:
        def create(self, **kwargs: Any) -> Any:
            # Server-side refusal fallback: if the model declines, the API retries on a fallback model.
            return client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
            )

    return _Client()


class AnalystAgent:
    def __init__(self, messages_client: MessagesClient | None = None, model: str = DEFAULT_MODEL,
                 log: bool = True) -> None:
        self._client = messages_client
        self.model = model
        self.log = log

    @property
    def client(self) -> MessagesClient:
        if self._client is None:
            self._client = _anthropic_messages()
        return self._client

    def ask(self, question: str) -> AgentResult:
        started = time.monotonic()
        toolbox = Toolbox()
        messages: list[dict] = [{"role": "user", "content": question}]
        result = AgentResult(run_id=uuid.uuid4().hex[:12], question=question, model=self.model,
                             answer=None, tool_calls=toolbox.calls, turns=0, latency_seconds=0.0)
        try:
            for _ in range(MAX_TURNS):
                result.turns += 1
                response = self.client.create(
                    model=self.model,
                    max_tokens=16000,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    output_config={"effort": "medium"},
                    messages=messages,
                )
                usage = getattr(response, "usage", None)
                result.input_tokens += getattr(usage, "input_tokens", 0) or 0
                result.output_tokens += getattr(usage, "output_tokens", 0) or 0
                result.stop_reason = response.stop_reason

                if response.stop_reason == "refusal":
                    result.error = "The model declined to answer."
                    break
                if response.stop_reason == "max_tokens":
                    result.error = "The response hit max_tokens."
                    break

                messages.append({"role": "assistant", "content": response.content})
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    if toolbox.submission is None:
                        # The model answered in prose. Ask it to use submit_answer so the log is structured.
                        messages.append({"role": "user", "content": "Please call submit_answer with your answer."})
                        continue
                    break

                tool_results = []
                for block in tool_uses:
                    content, is_error = toolbox.execute(block.name, dict(block.input))
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                         "content": content, "is_error": is_error})
                messages.append({"role": "user", "content": tool_results})
                if toolbox.submission is not None:
                    break
            else:
                result.error = f"No answer after {MAX_TURNS} turns."
        except Exception as e:  # network or API errors are logged with the run, then re-raised
            result.error = f"{type(e).__name__}: {e}"
            raise
        finally:
            result.answer = toolbox.submission
            result.latency_seconds = round(time.monotonic() - started, 2)
            result.paths = sorted({c.path for c in toolbox.calls if c.path})
            if self.log:
                write_log(result)
        return result


def write_log(result: AgentResult) -> None:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = AGENT_LOG_DIR / f"answers_{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(result.to_log(), default=str) + "\n")
