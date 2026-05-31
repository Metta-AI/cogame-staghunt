"""Tests for the reporter facts + deterministic fallback narrative + zip."""

import io
import json
import zipfile

from staghunt_tools.episode import from_results
from staghunt_tools.reporter import REPORTER_ID, build_facts, build_report, render_fallback_markdown

from test_episode import build_results


def _stats(captures, scores):
    return from_results(build_results(4, captures, scores=scores))


def test_build_facts_winner_and_collaborations():
    facts = build_facts(_stats([(4, [0, 1, 2, 3])] * 2, [20, 10, 5, 5]), episode_id="ereq_test")
    assert facts["episode_id"] == "ereq_test"
    assert facts["outcome"]["winner"]["name"] == "p0"
    assert facts["outcome"]["margin"] == 10
    assert not facts["outcome"]["tie"]
    # 4-player kills → all 6 pairs collaborated.
    assert len(facts["collaborations"]) == 6
    assert facts["collaborations"][0]["shared_kills"] == 2


def test_build_facts_tie():
    facts = build_facts(_stats([(0, [0]), (0, [1])], [3, 3, 0, 0]), episode_id="e")
    assert facts["outcome"]["tie"] is True
    assert facts["outcome"]["winner"] is None


def test_fallback_markdown_mentions_winner_and_starts_with_heading():
    facts = build_facts(_stats([(4, [0, 1, 2, 3])], [9, 4, 2, 1]), episode_id="e1")
    md = render_fallback_markdown(facts)
    assert md.startswith("# Stag Hunt")
    assert "p0" in md
    assert "interest score" in md.lower()


def test_build_report_no_llm_produces_valid_zip():
    facts = build_facts(_stats([(4, [0, 1, 2, 3])], [9, 4, 2, 1]), episode_id="e1")
    zip_bytes, source = build_report(facts, use_llm=False, model="unused")
    assert source == "fallback"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert {"manifest.json", "report.md", "stats.json"} <= names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["reporter_id"] == REPORTER_ID
        assert manifest["render"] == "report.md"
        stats_payload = json.loads(zf.read("stats.json"))
        assert stats_payload["narration_source"] == "fallback"
        assert stats_payload["interest"]["score"] >= 0.0


def test_report_zip_is_deterministic():
    facts = build_facts(_stats([(3, [0, 1, 2])], [7, 5, 3, 0]), episode_id="e2")
    a, _ = build_report(facts, use_llm=False, model="unused")
    b, _ = build_report(facts, use_llm=False, model="unused")
    assert a == b
