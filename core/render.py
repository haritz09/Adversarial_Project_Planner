from __future__ import annotations

from collections.abc import Mapping

from core.models import DebateResult


def render_debate_flow(
    debates: Mapping[str, DebateResult],
    titles: Mapping[str, str] | None = None,
    title: str = "Debate Flow",
) -> str:
    titles = titles or {}
    lines: list[str] = [f"# {title}", ""]

    for name, debate in debates.items():
        heading = titles.get(name, debate.get("topic") or name)
        lines += [f"## {heading}", ""]

        if debate.get("skipped"):
            lines += ["_Skipped: the decision was predefined by the user._", ""]
            continue

        turns = debate.get("turns", [])
        rounds = sorted({int(turn.get("round", 0)) for turn in turns})
        for round_index in rounds:
            lines += [f"### Round {round_index}", ""]
            for turn in (t for t in turns if int(t.get("round", 0)) == round_index):
                lines += [f"**Agent {turn['agent']}**", "", str(turn.get("content", "")), ""]

        verdict = debate.get("verdict") or {}
        lines += ["### Judge Decision", ""]
        lines.append(f"**Winner:** {verdict.get('winner') or debate.get('winner') or 'tie'}")
        lines.append("")
        decision = verdict.get("winning_stack") or ""
        if decision:
            lines += [f"**Decision:** {decision}", ""]
        lines += [f"**Rationale:** {verdict.get('rationale', 'N/A')}", ""]

        scores = debate.get("scores") or {}
        if scores:
            lines += [
                "| Agent | Score |",
                "|---|---|",
                f"| Agent A | {scores.get('agent_a', 'n/a')}/10 |",
                f"| Agent B | {scores.get('agent_b', 'n/a')}/10 |",
                "",
            ]

        rounds_completed = debate.get("rounds_completed", 0)
        status = debate.get("status", "decided")
        lines += [f"_Rounds: {rounds_completed} · Status: {status}_", ""]

    return "\n".join(lines).rstrip() + "\n"
