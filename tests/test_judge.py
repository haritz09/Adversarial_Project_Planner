# tests/test_judge.py
"""
Run all tests:        python tests/test_judge.py
Run only live tests:  python tests/test_judge.py live
Run only unit tests:  python tests/test_judge.py unit
"""
import sys
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import MagicMock, patch
from agents.judge import (
    build_judge_prompt,
    parse_judge_response,
    debate1_judge,
    should_continue_debate1,
    MAX_ROUNDS,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

BASE_STATE = {
    "project_context": {
        "goal": "real-time chat app",
        "timeline": "3 weeks",
        "team_size": 2,
        "constraints": ["must use existing auth system"],
        "stack": None,
        "methodology": None,
    },
    "user_provided_fields": {
        "goal": True, "timeline": True, "team_size": True,
        "stack": False, "methodology": False,
    },
    "debate1_arguments": [
        {"agent": "A", "argument": "React + Node.js + Socket.io gives full control over WebSocket connections and scales well with 2 devs in 3 weeks.", "round": 1},
        {"agent": "B", "argument": "Firebase handles real-time out of the box, reducing backend complexity significantly for a 2-person team on a tight timeline.", "round": 1},
    ],
    "debate1_rounds": 2,
}

STATE_MAX_ROUNDS = {
    **BASE_STATE,
    "debate1_rounds": MAX_ROUNDS + 1,
}

STATE_ROUND1 = {
    **BASE_STATE,
    "debate1_rounds": 1,
    "debate1_arguments": [
        {"agent": "A", "argument": "I propose React + Node.js.", "round": 1},
    ],
}

VALID_JUDGE_JSON = json.dumps({
    "needs_another_round": False,
    "winner": "B",
    "winning_stack": "Firebase + React",
    "rationale": "Firebase reduces backend complexity for a 2-person team on a 3-week timeline.",
    "agent_a_score": 7,
    "agent_b_score": 9,
})

CONTINUE_JUDGE_JSON = json.dumps({
    "needs_another_round": True,
    "reason_for_continuing": "Neither agent addressed scalability beyond MVP.",
    "agent_a_score": 6,
    "agent_b_score": 6,
})


# ══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — no LLM calls
# ══════════════════════════════════════════════════════════════════════════════

def test_prompt_contains_project_info():
    prompt = build_judge_prompt(BASE_STATE)
    assert "real-time chat app" in prompt
    assert "3 weeks" in prompt
    assert "must use existing auth system" in prompt
    print("✅ Prompt contains project info")

def test_prompt_contains_debate_history():
    prompt = build_judge_prompt(BASE_STATE)
    assert "Agent A" in prompt
    assert "Agent B" in prompt
    assert "Socket.io" in prompt
    assert "Firebase" in prompt
    print("✅ Prompt contains full debate history")

def test_prompt_grouped_by_round():
    prompt = build_judge_prompt(BASE_STATE)
    assert "Round 1" in prompt
    print("✅ Prompt groups arguments by round")

def test_parse_valid_json():
    result = parse_judge_response(VALID_JUDGE_JSON)
    assert result["needs_another_round"] == False
    assert result["winner"] == "B"
    assert result["winning_stack"] == "Firebase + React"
    assert result["agent_a_score"] == 7
    assert result["agent_b_score"] == 9
    print("✅ Parses valid JSON correctly")

def test_parse_json_with_markdown_fences():
    wrapped = f"Here is my decision:\n```json\n{VALID_JUDGE_JSON}\n```\nHope this helps."
    result = parse_judge_response(wrapped)
    assert result["winner"] == "B"
    print("✅ Parses JSON wrapped in markdown fences")

def test_parse_json_with_preamble():
    wrapped = f"After careful analysis:\n{VALID_JUDGE_JSON}\nThat concludes my evaluation."
    result = parse_judge_response(wrapped)
    assert result["needs_another_round"] == False
    print("✅ Parses JSON with surrounding text")

def test_parse_invalid_json_returns_fallback():
    result = parse_judge_response("The winner is clearly Agent A and I cannot decide otherwise.")
    assert result["needs_another_round"] == False
    assert result["winner"] == "tie"
    assert "rationale" in result
    print("✅ Returns safe fallback on unparseable response")

def test_should_continue_when_true():
    state = {**BASE_STATE, "debate1_needs_another_round": True}
    assert should_continue_debate1(state) == "debate1_A"
    print("✅ should_continue_debate1 returns debate1_A when another round needed")

def test_should_conclude_when_false():
    state = {**BASE_STATE, "debate1_needs_another_round": False}
    assert should_continue_debate1(state) == "architecture_generator"
    print("✅ should_continue_debate1 returns architecture_generator when debate concludes")

def test_should_conclude_when_missing():
    # Default should be to conclude, not loop
    assert should_continue_debate1(BASE_STATE) == "architecture_generator"
    print("✅ should_continue_debate1 defaults to conclude when field missing")

def test_judge_forces_conclusion_at_max_rounds():
    result = debate1_judge(STATE_MAX_ROUNDS)
    assert result["debate1_needs_another_round"] == False
    assert result["debate1_decision"] == "max_rounds_reached"
    assert result["current_node"] == "debate1_judge"
    print(f"✅ Judge forces conclusion when rounds > MAX_ROUNDS ({MAX_ROUNDS})")

def test_judge_mocked_conclude():
    """Judge decides to conclude — mock LLM response."""
    with patch("agents.judge.llm_judge") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content=VALID_JUDGE_JSON)
        result = debate1_judge(BASE_STATE)

    assert result["debate1_needs_another_round"] == False
    assert result["debate1_winner"] == "B"
    assert result["debate1_winning_stack"] == "Firebase + React"
    assert "Firebase" in result["debate1_judge_rationale"]
    assert result["debate1_agent_a_score"] == 7
    assert result["debate1_agent_b_score"] == 9
    assert result["current_node"] == "debate1_judge"
    print("✅ [MOCK] Judge correctly populates state when concluding")

def test_judge_mocked_continue():
    """Judge decides another round is needed — mock LLM response."""
    with patch("agents.judge.llm_judge") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content=CONTINUE_JUDGE_JSON)
        result = debate1_judge(BASE_STATE)

    assert result["debate1_needs_another_round"] == True
    assert result["current_node"] == "debate1_judge"
    print("✅ [MOCK] Judge correctly signals another round needed")

def test_judge_mocked_cannot_exceed_max_rounds():
    """Even if LLM says continue, judge must stop at MAX_ROUNDS."""
    state_at_max = {**BASE_STATE, "debate1_rounds": MAX_ROUNDS}
    with patch("agents.judge.llm_judge") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content=CONTINUE_JUDGE_JSON)
        result = debate1_judge(state_at_max)

    assert result["debate1_needs_another_round"] == False
    print(f"✅ [MOCK] Judge ignores LLM 'continue' signal at MAX_ROUNDS ({MAX_ROUNDS})")


# ══════════════════════════════════════════════════════════════════════════════
# LIVE TESTS — real Groq API calls
# ══════════════════════════════════════════════════════════════════════════════

def test_judge_live_conclude():
    """Live call — judge should be able to reach a conclusion after round 2."""
    print("\n   Calling Groq 70B (this may take a few seconds)...")
    result = debate1_judge(BASE_STATE)

    assert "debate1_needs_another_round" in result
    assert "debate1_winner" in result
    assert "debate1_judge_rationale" in result
    assert result["debate1_judge_rationale"] != ""
    assert result["current_node"] == "debate1_judge"
    assert isinstance(result.get("debate1_agent_a_score"), (int, float))
    assert isinstance(result.get("debate1_agent_b_score"), (int, float))

    print(f"   Winner: {result.get('debate1_winner')}")
    print(f"   Stack:  {result.get('debate1_winning_stack')}")
    print(f"   Rationale: {result.get('debate1_judge_rationale')[:150]}...")
    print(f"   Scores — A: {result.get('debate1_agent_a_score')} | B: {result.get('debate1_agent_b_score')}")
    print(f"   Another round: {result['debate1_needs_another_round']}")
    print("✅ [LIVE] Judge produced a valid decision")

def test_judge_live_round1_may_continue():
    """Live call — after only 1 argument from A, judge may want another round."""
    print("\n   Calling Groq 70B with incomplete debate (round 1 only)...")
    result = debate1_judge(STATE_ROUND1)

    assert "debate1_needs_another_round" in result
    assert result["current_node"] == "debate1_judge"
    print(f"   Another round requested: {result['debate1_needs_another_round']}")
    print("✅ [LIVE] Judge handled early-round state correctly")

def test_conditional_edge_live():
    """Live call — verify the full judge → conditional edge flow."""
    print("\n   Testing full judge + conditional edge flow...")
    result = debate1_judge(BASE_STATE)
    next_node = should_continue_debate1(result)

    assert next_node in ["debate1_A", "architecture_generator"]
    print(f"   Next node: {next_node}")
    print("✅ [LIVE] Conditional edge resolves correctly from live judge output")


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

UNIT_TESTS = [
    test_prompt_contains_project_info,
    test_prompt_contains_debate_history,
    test_prompt_grouped_by_round,
    test_parse_valid_json,
    test_parse_json_with_markdown_fences,
    test_parse_json_with_preamble,
    test_parse_invalid_json_returns_fallback,
    test_should_continue_when_true,
    test_should_conclude_when_false,
    test_should_conclude_when_missing,
    test_judge_forces_conclusion_at_max_rounds,
    test_judge_mocked_conclude,
    test_judge_mocked_continue,
    test_judge_mocked_cannot_exceed_max_rounds,
]

LIVE_TESTS = [
    test_judge_live_conclude,
    test_judge_live_round1_may_continue,
    test_conditional_edge_live,
]

def run(tests: list, label: str):
    print(f"\n{'═' * 60}")
    print(f"{label}")
    print(f"{'═' * 60}")
    passed = 0
    failed = 0
    for t in tests:
        try:
            print(f"\n▶ {t.__name__}")
            t()
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed += 1
    print(f"\n{'─' * 60}")
    print(f"{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    total_failures = 0

    if mode in ("all", "unit"):
        total_failures += run(UNIT_TESTS, "UNIT TESTS (no LLM)")

    if mode in ("all", "live"):
        total_failures += run(LIVE_TESTS, "LIVE TESTS (Groq API)")

    print(f"\n{'═' * 60}")
    if total_failures == 0:
        print("ALL TESTS PASSED ✅")
    else:
        print(f"{total_failures} TEST(S) FAILED ❌")
        sys.exit(1)