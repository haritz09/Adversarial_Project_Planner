from __future__ import annotations

import argparse
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from dotenv import load_dotenv
from langgraph.types import Command

import observability
from graph.pipeline import build_graph
from sinks.registry import available_sinks

load_dotenv()

DEFAULT_DESCRIPTION = "Build a real-time chat app in 3 weeks with 2 developers"

NODE_LABELS = {
    "intake_node": "📥 Understanding your project",
    "prepare_debates": "🧩 Preparing debate inputs",
    "debater_a": "🔵 Agent A arguing",
    "debater_b": "🔴 Agent B responding",
    "judge": "⚖️  Judge evaluating the debate",
    "skip": "⏭️  Debate skipped (predefined)",
    "architecture_generator": "🏗️  Generating architectural overview",
    "scope_generator": "🎯 Defining scope & objectives",
    "plan_generator": "📅 Building project plan",
    "debate_flow_generator": "💬 Compiling debate transcript",
    "export_node": "📝 Exporting documents",
}

class ProgressPrinter:
    def __init__(self) -> None:
        self.last_round = 0

    def __call__(self, node: str, payload: Mapping[str, Any], namespace: Iterable[str]) -> None:
        inside_subgraph = bool(tuple(namespace))

        if node == "debater_a" and payload.get("_turns"):
            round_index = int(payload["_turns"][-1].get("round", 1))
            if round_index != self.last_round:
                self.last_round = round_index
                print(f"\n  ── Round {round_index} ──────────────────")

        indent = "    " if inside_subgraph else "  "
        print(f"{indent}{NODE_LABELS.get(node, node)}")

        if node == "judge":
            self._print_judge(payload)
        if node == "export_node":
            result = payload.get("export_result") or {}
            print(f"     → {result.get('sink')}: {result.get('location')}")

    @staticmethod
    def _print_judge(payload: Mapping[str, Any]) -> None:
        debates = payload.get("debates") or {}
        for debate in debates.values():
            verdict = debate.get("verdict") or {}
            winner = verdict.get("winner") or debate.get("winner") or "tie"
            decision = verdict.get("winning_stack") or ""
            line = f"     → Winner: Agent {winner}"
            if decision:
                line += f" — {decision}"
            print(line)
        if not debates and payload.get("_needs_another_round"):
            reason = str(payload.get("_continue_reason") or "")[:100]
            print(f"     → Another round needed: {reason}")

def run_pipeline(graph, inputs: Any, config: Mapping[str, Any], printer: ProgressPrinter) -> None:
    while True:
        interrupted = False
        for namespace, update in graph.stream(
            inputs, config=config, stream_mode="updates", subgraphs=True
        ):
            if "__interrupt__" in update:
                question = update["__interrupt__"][0].value
                print(f"\n❓ {question}")
                answer = input("Your answer: ").strip()
                inputs = Command(resume=answer)
                interrupted = True
                break

            for node, payload in update.items():
                printer(node, payload or {}, namespace)

        if not interrupted:
            return

def _print_results(final: Mapping[str, Any]) -> None:
    print("\n" + "─" * 55)
    print("✅ Pipeline complete!\n")

    result = final.get("export_result") or {}
    if result:
        print(f"📄 Exported with '{result.get('sink')}': {result.get('location')}")
        if result.get("fallback_from"):
            print(f"   (fallback from {result['fallback_from']}: {result.get('fallback_reason')})")
        for key, url in (result.get("urls") or {}).items():
            print(f"   - {key}: {url}")

    for name, debate in (final.get("debates") or {}).items():
        verdict = debate.get("verdict") or {}
        print(f"\n⚖️  {name}")
        print(f"   Winner:  Agent {verdict.get('winner') or debate.get('winner') or 'tie'}")
        if verdict.get("winning_stack"):
            print(f"   Decision: {verdict['winning_stack']}")
        scores = debate.get("scores") or {}
        if scores:
            print(f"   Scores:  A={scores.get('agent_a')}/10  B={scores.get('agent_b')}/10")
        print(f"   Rounds:  {debate.get('rounds_completed', 0)} ({debate.get('status')})")
        if debate.get("cost_usd"):
            print(f"   Cost:    ${debate['cost_usd']:.6f}")
    print()

def _score_run(trace: observability.TraceSession, final: Mapping[str, Any]) -> None:
    if not trace.enabled:
        if trace.reason and trace.reason != "disabled":
            print(f"⚠️  Langfuse disabled: {trace.reason}")
        return

    for name, debate in (final.get("debates") or {}).items():
        scores = debate.get("scores") or {}
        observability.score(
            trace, f"{name}.agent_a_score", scores.get("agent_a", 5) / 10,
            comment=f"Judge score for Agent A — winner: {debate.get('winner')}",
        )
        observability.score(
            trace, f"{name}.agent_b_score", scores.get("agent_b", 5) / 10,
            comment="Judge score for Agent B",
        )
        observability.score(
            trace, f"{name}.rounds", debate.get("rounds_completed", 1),
            comment="Rounds needed to reach a verdict",
        )
        if debate.get("cost_usd"):
            observability.score(trace, f"{name}.cost_usd", debate["cost_usd"])

    observability.finish(trace)
    if trace.scores:
        print(f"📊 {len(trace.scores)} scores sent to Langfuse (trace {trace.trace_id})")

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adversarial project planner")
    parser.add_argument("--describe", default=None, help="Project description")
    parser.add_argument(
        "--sink",
        default="auto",
        choices=["auto", *available_sinks()],
        help="Export destination (auto picks Notion when configured, else Markdown)",
    )
    parser.add_argument("--output-dir", default="output", help="Directory for file sinks")
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Identifier for this run (groups traces and names the export folder)",
    )
    parser.add_argument("--no-trace", action="store_true", help="Disable Langfuse")
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    print("\n╔══════════════════════════════════════════╗")
    print("║     Adversarial Project Planner 🤖       ║")
    print("╚══════════════════════════════════════════╝\n")

    description = (args.describe or "").strip()
    if not description:
        description = input("Describe your project: ").strip() or DEFAULT_DESCRIPTION

    thread_id = args.thread_id or f"run-{uuid.uuid4().hex[:8]}"
    trace = observability.start_trace(
        "Adversarial Project Planner",
        session_id=f"run-{description[:40].replace(' ', '-')}",
        enabled=False if args.no_trace else None,
    )

    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "run_name": "Adversarial Project Planner",
        "metadata": trace.metadata(),
    }
    if trace.handler is not None:
        config["callbacks"] = [trace.handler]

    graph = build_graph()
    inputs = {
        "raw_input": description,
        "run_id": thread_id,
        "export_config": {"sink": args.sink, "output_dir": args.output_dir},
    }

    print(f"\n🚀 Starting pipeline (thread: {thread_id})...\n")
    run_pipeline(graph, inputs, config, ProgressPrinter())

    final = graph.get_state(config).values
    _print_results(final)
    _score_run(trace, final)

if __name__ == "__main__":
    main()
