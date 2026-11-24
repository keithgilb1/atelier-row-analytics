"""The eval answer key must resolve to one number per question (no API call needed)."""

import pytest

from atelier.agent.eval import CASES, score


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_answer_key_resolves(case):
    v = case.expected()
    assert v is None or isinstance(v, float)


def test_scoring_accepts_percent_or_ratio_and_rejects_pii():
    case = next(c for c in CASES if c.id == "comp_fy26")
    exp = case.expected()
    assert score(case, exp, exp, "")
    assert score(case, exp, exp * 100, "")
    assert not score(case, exp, -0.60, "")
    pii = next(c for c in CASES if c.id == "pii")
    assert score(pii, None, None, "Customer contact details are not available.")
    assert not score(pii, None, None, "Call +1 555 123 4567")
