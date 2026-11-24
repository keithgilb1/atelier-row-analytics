"""The agent loop, tools and logging, driven by a scripted model so it runs without an API key."""

import json
from types import SimpleNamespace as NS

from atelier.agent import agent as agent_mod
from atelier.agent.agent import AnalystAgent


def tool_use(i, name, **inp):
    return NS(type="tool_use", id=f"tu_{i}", name=name, input=inp)


def reply(*blocks, stop="tool_use"):
    return NS(content=list(blocks), stop_reason=stop, usage=NS(input_tokens=100, output_tokens=20))


class ScriptedClient:
    """Plays back a fixed list of model turns and keeps the requests it received."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.turns.pop(0)


def test_governed_question_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "AGENT_LOG_DIR", tmp_path)
    client = ScriptedClient([
        reply(tool_use(1, "list_metrics")),
        reply(tool_use(2, "query_metrics", metrics=["comp_store_sales_growth"],
                       group_by=["metric_time__fiscal_year"], where=[], order_by=[], limit=20)),
        reply(tool_use(3, "submit_answer", answer="FY2026 comp store sales grew 5.2%.", headline_value=0.0516,
                       unit="ratio", metrics_used=["comp_store_sales_growth"], caveats=[])),
    ])
    result = AnalystAgent(messages_client=client).ask("What was comp store sales growth in FY2026?")

    assert result.answer.headline_value == 0.0516
    assert result.paths == ["governed"]
    governed_call = result.tool_calls[1]
    assert governed_call.sql and "fct_comp_sales_daily" in governed_call.sql
    assert governed_call.row_count == 7

    # The tool result the model saw contains the governed number.
    tool_result = client.requests[2]["messages"][-1]["content"][0]
    rows = dict(json.loads(tool_result["content"])["rows"])
    assert abs(rows["FY2026"] - 0.05157185) < 1e-6

    log = [json.loads(line) for line in next(tmp_path.glob("answers_*.jsonl")).read_text().splitlines()]
    assert log[0]["question"].startswith("What was comp")
    assert log[0]["answer"]["metrics_used"] == ["comp_store_sales_growth"]
    assert log[0]["tool_calls"][1]["sql"]


def test_blocked_sql_is_returned_to_the_model_as_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "AGENT_LOG_DIR", tmp_path)
    client = ScriptedClient([
        reply(tool_use(1, "run_sql", sql="select customer_name, customer_phone from raw.main.customers")),
        reply(tool_use(2, "submit_answer", answer="Customer contact details are not available.",
                       headline_value=None, unit=None, metrics_used=[], caveats=["PII is excluded"])),
    ])
    result = AnalystAgent(messages_client=client).ask("Give me the phone numbers of our top buyers")

    sent_back = client.requests[1]["messages"][-1]["content"][0]
    assert sent_back["is_error"] is True
    assert "outside the marts schema" in sent_back["content"]
    assert result.tool_calls[0].error
    assert result.answer.headline_value is None


def test_prose_answer_is_nudged_to_submit_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "AGENT_LOG_DIR", tmp_path)
    client = ScriptedClient([
        reply(NS(type="text", text="About 40%."), stop="end_turn"),
        reply(tool_use(1, "submit_answer", answer="Gross margin is about 40%.", headline_value=0.395,
                       unit="ratio", metrics_used=["gross_margin_pct"], caveats=[])),
    ])
    result = AnalystAgent(messages_client=client).ask("What is our gross margin?")
    assert "submit_answer" in client.requests[1]["messages"][-1]["content"]
    assert result.answer.metrics_used == ["gross_margin_pct"]


def test_refusal_is_logged_without_an_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "AGENT_LOG_DIR", tmp_path)
    client = ScriptedClient([reply(stop="refusal")])
    result = AnalystAgent(messages_client=client).ask("...")
    assert result.answer is None and "declined" in result.error
