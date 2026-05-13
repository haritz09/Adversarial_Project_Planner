# main.py
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from langgraph.types import Command
from graph.pipeline import graph
from langfuse.langchain import CallbackHandler
from langfuse import Langfuse


import uuid

# ── Langfuse setup ────────────────────────────────────────────────────────────

langfuse_handler = CallbackHandler()
langfuse_client = Langfuse()

# ── Config ────────────────────────────────────────────────────────────────────

# Create a single run_id for the entire session so it's grouped under one trace
session_run_id = str(uuid.uuid4())

config = {
    "configurable": {"thread_id": "run-1"},
    "callbacks": [langfuse_handler],
    "run_name": "Adversarial Project Planner",
    "run_id": uuid.UUID(session_run_id)
}


# ── Langfuse scoring ──────────────────────────────────────────────────────────

def score_debate(final_state: dict) -> None:
    try:
        trace_id = session_run_id
        if not trace_id:
            print("⚠️  No trace ID available — skipping scores")
            return

        langfuse_client.create_score(         
            trace_id=trace_id,
            name="agent_a_score",
            value=final_state.get("debate1_agent_a_score", 5) / 10,
            comment=f"Judge score for Agent A — winner: {final_state.get('debate1_winner')}",
        )
        langfuse_client.create_score(      
            trace_id=trace_id,
            name="agent_b_score",
            value=final_state.get("debate1_agent_b_score", 5) / 10,
            comment=f"Judge score for Agent B — stack: {final_state.get('debate1_winning_stack')}",
        )
        langfuse_client.create_score(          
            trace_id=trace_id,
            name="debate_rounds",
            value=final_state.get("debate1_rounds", 1),
            comment="Number of rounds needed to reach consensus",
        )
        langfuse_client.flush()        
        print("📊 Scores sent to Langfuse")
    except Exception as e:
        print(f"⚠️  Langfuse scoring failed: {e}")


# ── Node display names ────────────────────────────────────────────────────────

NODE_LABELS = {
    "intake_node":             "📥 Understanding your project",
    "debate1_A":               "🔵 Agent A arguing tech stack",
    "debate1_B":               "🔴 Agent B responding",
    "debate1_judge":           "⚖️  Judge evaluating debate",
    "architecture_generator":  "🏗️  Generating architectural overview",
    "scope_generator":         "🎯 Defining scope & objectives",
    "plan_generator":          "📅 Building project plan",
    "debate_flow_generator":   "💬 Compiling debate transcript",
    "notion_writer":           "📝 Writing to Notion",
}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║     Adversarial Project Planner 🤖       ║")
    print("╚══════════════════════════════════════════╝\n")

    user_input = input("Describe your project: ").strip()
    if not user_input:
        user_input = "Build a real-time chat app in 3 weeks with 2 developers"

    # Update session_id now that we have user_input
    langfuse_handler.session_id = f"run-{user_input[:40].replace(' ', '-')}"

    print("\n🚀 Starting pipeline...\n")

    inputs = {"raw_input": user_input}
    current_round = 0

    while True:
        interrupted = False

        for step in graph.stream(inputs, config=config, stream_mode="updates"):
            node = list(step.keys())[0]

            if node == "__interrupt__":
                interrupted = True
                question = step["__interrupt__"][0].value
                print(f"\n❓ {question}")
                answer = input("Your answer: ").strip()
                inputs = Command(resume=answer)
                break

            # Track debate rounds for display
            if node in ("debate1_A", "debate1_B", "debate2_A", "debate2_B"):
                state_data = step.get(node, {})
                round_num = state_data.get("debate1_rounds", state_data.get("debate2_rounds", 1))
                if node.endswith("_A") and round_num != current_round:
                    current_round = round_num
                    print(f"\n  ── Round {current_round} ──────────────────")

            label = NODE_LABELS.get(node, f"✅ {node}")
            print(f"  {label}")

            # Show judge decision inline
            if node == "debate1_judge":
                state_data = step.get(node, {})
                winner = state_data.get("debate1_winner")
                stack = state_data.get("debate1_winning_stack")
                needs_more = state_data.get("debate1_needs_another_round", False)
                if needs_more:
                    reason = state_data.get("debate1_judge_continue_reason", "")
                    print(f"     → Another round needed: {reason[:80]}...")
                elif winner and stack:
                    print(f"     → Winner: Agent {winner} — {stack}")

        if not interrupted:
            break

    # ── Results ───────────────────────────────────────────────────────────────
    final_state = graph.get_state(config).values

    print("\n" + "─" * 50)
    print("✅ Pipeline complete!\n")

    # Notion links
    notion_urls = final_state.get("notion_urls", {})
    if notion_urls:
        print("📄 Notion pages created:")
        page_names = {
            "root":         "  Project Root",
            "architecture": "  1. Architectural Overview",
            "scope":        "  2. Scope & Objectives",
            "plan_root":    "  3. Project Plan",
            "plan":         "  3.1 Full Plan",
            "flow":         "  4. Debate Flow",
        }
        for key, url in notion_urls.items():
            name = page_names.get(key, f"  {key}")
            print(f"{name}: {url}")

    # Debate summary
    winner = final_state.get("debate1_winner")
    stack = final_state.get("debate1_winning_stack")
    rounds = final_state.get("debate1_rounds", 1)
    a_score = final_state.get("debate1_agent_a_score")
    b_score = final_state.get("debate1_agent_b_score")

    if winner and stack:
        print(f"\n⚖️  Debate summary:")
        print(f"   Winner:  Agent {winner}")
        print(f"   Stack:   {stack}")
        if a_score and b_score:
            print(f"   Scores:  A={a_score}/10  B={b_score}/10")

    # Langfuse scores
    score_debate(final_state)
    print("\n")


if __name__ == "__main__":
    main()