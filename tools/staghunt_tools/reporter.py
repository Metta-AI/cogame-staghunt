"""stag_hunt reporter — sports-commentator / newspaper write-up of an episode.

Implements the Coworld reporter contract (``docs/roles/REPORTER.md`` in
``Metta-AI/metta``): a short-lived process that reads an episode bundle from
``COGAME_EPISODE_BUNDLE_URI`` and writes a report zip to ``COGAME_REPORT_URI``.

Hybrid design:

  * Deterministic facts are computed from ``results.json`` via ``episode.py``
    (reward-agnostic — actual scores and co-capture structure, never hardcoded
    prey points). These go into ``stats.json`` verbatim.
  * The prose narrative (``report.md``) is written by Claude via AWS Bedrock,
    grounded strictly in those facts. On any Bedrock unavailability or error,
    a deterministic templated narrative is emitted instead, so the reporter
    never fails.

Env:
  STAGHUNT_REPORTER_MODEL  Bedrock model / inference-profile id
                           (default: us.anthropic.claude-opus-4-7).
  AWS_REGION               Bedrock region (honored by the AWS SDK / client).
  STAGHUNT_REPORTER_NO_LLM if set (to any non-empty value), skip Bedrock and
                           always use the deterministic narrative. Useful for
                           offline/CI runs.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from ._sdk import BundleReader, OutputManifest, build_report_zip, write_uri
from .episode import PREY_KINDS, EpisodeStats, from_results
from .grader import grade_episode

REPORTER_ID = "stag-hunt-commentator"
DEFAULT_MODEL = "us.anthropic.claude-opus-4-7"
MAX_TOKENS = 1400


# ---------- deterministic facts (the ground truth the prose must respect) ----------


def build_facts(stats: EpisodeStats, episode_id: str | None) -> dict[str, Any]:
    """Assemble a compact, JSON-serializable fact sheet from the episode.

    Every number here comes from the data. The reporter — LLM or template —
    must not introduce facts beyond these.
    """
    standings = sorted(stats.players, key=lambda p: p.score, reverse=True)
    top = standings[0].score if standings else 0
    leaders = [p for p in standings if p.score == top and top > 0]
    runner_up = standings[1].score if len(standings) > 1 else 0

    grade = grade_episode(stats)

    return {
        "episode_id": episode_id,
        "num_players": stats.num_players,
        "standings": [
            {
                "slot": p.slot,
                "name": p.name,
                "score": p.score,
                "total_catches": p.total_catches,
                "catches_by_kind": p.catches_by_kind(),
            }
            for p in standings
        ],
        "outcome": {
            "tie": len(leaders) > 1,
            "winner": None if (len(leaders) != 1) else {"name": leaders[0].name, "slot": leaders[0].slot},
            "top_score": top,
            "margin": (top - runner_up) if (len(leaders) == 1) else 0,
        },
        "catches_by_kind_total": stats.catches_by_kind(),
        "collaborations": [
            {
                "a": stats.players[c.a].name if c.a < stats.num_players else f"slot {c.a}",
                "b": stats.players[c.b].name if c.b < stats.num_players else f"slot {c.b}",
                "shared_kills": c.shared,
            }
            for c in stats.shared_pairs()[:8]
        ],
        "rounds": {
            "count": len(stats.rounds),
            "scores": stats.rounds,
            "lead_changes": stats.lead_changes(),
        },
        "interest": {
            "score": round(grade.score, 4),
            "components": {k: round(v, 4) for k, v in grade.components.items()},
        },
    }


# ---------- deterministic fallback narrative ----------


def render_fallback_markdown(facts: dict[str, Any]) -> str:
    ep = facts.get("episode_id") or "unknown"
    standings = facts["standings"]
    outcome = facts["outcome"]
    kinds = facts["catches_by_kind_total"]
    collabs = facts["collaborations"]

    lines = [f"# Stag Hunt — Episode {ep}", ""]

    if outcome["tie"]:
        lines.append(f"**A dead heat.** {len(standings)} hunters tied at the top with {outcome['top_score']} points.")
    elif outcome["winner"]:
        w = outcome["winner"]
        margin = outcome["margin"]
        lead = "in a runaway" if margin >= max(outcome["top_score"] // 2, 1) else "by a whisker" if margin <= 2 else f"by {margin}"
        lines.append(f"**{w['name']} takes it{'' if margin == 0 else f' {lead}'}** with {outcome['top_score']} points.")
    else:
        lines.append("**A quiet outing** — nobody put points on the board.")
    lines.append("")

    lines.append("## Final standings")
    lines.append("")
    lines.append("| # | Hunter | Score | Catches |")
    lines.append("| --- | --- | --- | --- |")
    for rank, s in enumerate(standings, 1):
        bk = ", ".join(f"{k} {v}" for k, v in s["catches_by_kind"].items() if v) or "—"
        lines.append(f"| {rank} | {s['name']} | {s['score']} | {bk} |")
    lines.append("")

    total_kinds = ", ".join(f"{k} ×{v}" for k, v in kinds.items() if v)
    if total_kinds:
        lines.append(f"**On the board:** {total_kinds}.")
        lines.append("")

    if collabs:
        lines.append("## Teamwork of the day")
        lines.append("")
        for c in collabs[:5]:
            lines.append(f"- **{c['a']} & {c['b']}** brought down {c['shared_kills']} together.")
        lines.append("")
    else:
        lines.append("No shared kills this episode — everyone hunted solo.")
        lines.append("")

    if facts["rounds"]["count"] > 1:
        lc = facts["rounds"]["lead_changes"]
        drama = "a back-and-forth affair" if lc >= 2 else "a steady grind" if lc == 0 else "one that swung once"
        lines.append(f"Across {facts['rounds']['count']} rounds it was {drama} ({lc} lead change{'s' if lc != 1 else ''}).")
        lines.append("")

    lines.append(f"_Collaboration interest score: {facts['interest']['score']:.2f} / 1.00._")
    return "\n".join(lines) + "\n"


# ---------- LLM narrative via AWS Bedrock ----------


def _system_prompt() -> str:
    return (
        "You are a lively sports commentator and newspaper sportswriter covering "
        "'Stag Hunt', a cooperative grid game where hunters surround prey together: "
        "rabbits go down solo, but boars, stags, moose, and elephants need coordinated "
        "multi-hunter encirclement. Bigger prey demand bigger coalitions.\n\n"
        "Write a punchy, vivid recap (a headline, a one-line lede, then 2-4 short "
        "paragraphs). Celebrate teamwork and clutch coordination as much as raw scoring.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY the facts in the provided JSON. Do not invent plays, names, "
        "moments, or numbers that aren't supported by the data.\n"
        "- The point values of prey are NOT given and you must NOT guess them; refer to "
        "scores and catch counts as reported.\n"
        "- Refer to hunters by their names. Output GitHub-flavored Markdown, starting "
        "with a single '# ' headline."
    )


def narrate_with_bedrock(facts: dict[str, Any], model: str) -> str | None:
    """Return Claude-written Markdown, or ``None`` if Bedrock is unavailable or
    errors (the caller then uses the deterministic narrative)."""
    try:
        from anthropic import AnthropicBedrock
    except Exception as exc:  # pragma: no cover - import guard
        print(f"[{REPORTER_ID}] anthropic[bedrock] unavailable ({exc}); using fallback", file=sys.stderr)
        return None

    try:
        client = AnthropicBedrock()  # region + creds from standard AWS env
        message = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Write the recap for this episode. Episode facts (JSON):\n\n"
                        + json.dumps(facts, indent=2, sort_keys=True)
                    ),
                }
            ],
        )
        text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text").strip()
        if not text:
            print(f"[{REPORTER_ID}] Bedrock returned empty text; using fallback", file=sys.stderr)
            return None
        if not text.startswith("#"):
            text = "# Stag Hunt recap\n\n" + text
        return text + "\n"
    except Exception as exc:
        print(f"[{REPORTER_ID}] Bedrock call failed ({exc}); using fallback", file=sys.stderr)
        return None


# ---------- orchestration ----------


def build_report(facts: dict[str, Any], *, use_llm: bool, model: str) -> tuple[bytes, str]:
    """Return (zip_bytes, narration_source) where source is 'bedrock' or 'fallback'."""
    narrative = narrate_with_bedrock(facts, model) if use_llm else None
    source = "bedrock" if narrative is not None else "fallback"
    if narrative is None:
        narrative = render_fallback_markdown(facts)

    stats_payload = {**facts, "reporter_id": REPORTER_ID, "narration_source": source}
    zip_bytes = build_report_zip(
        OutputManifest(reporter_id=REPORTER_ID, render="report.md"),
        [
            ("report.md", narrative.encode("utf-8")),
            ("stats.json", (json.dumps(stats_payload, indent=2, sort_keys=True) + "\n").encode("utf-8")),
        ],
    )
    return zip_bytes, source


def run(bundle_uri: str, report_uri: str) -> str:
    with BundleReader(bundle_uri) as bundle:
        inner = bundle.inner_manifest()
        if inner.status != "success":
            raise RuntimeError(f"bundle status={inner.status!r}; cannot report on a failed episode")
        results = bundle.read_json("results")
        episode_id = inner.ereq_id

    stats = from_results(results)
    facts = build_facts(stats, episode_id)

    use_llm = not os.environ.get("STAGHUNT_REPORTER_NO_LLM")
    model = os.environ.get("STAGHUNT_REPORTER_MODEL", DEFAULT_MODEL)
    zip_bytes, source = build_report(facts, use_llm=use_llm, model=model)

    write_uri(report_uri, zip_bytes, content_type="application/zip")
    print(f"[{REPORTER_ID}] wrote report ({source}) → {report_uri}", file=sys.stderr, flush=True)
    return source


def main() -> None:
    run(
        bundle_uri=os.environ["COGAME_EPISODE_BUNDLE_URI"],
        report_uri=os.environ["COGAME_REPORT_URI"],
    )


if __name__ == "__main__":
    main()
