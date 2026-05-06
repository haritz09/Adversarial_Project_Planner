# tests/test_debater.py
"""
Run with: python -m pytest tests/test_debater.py -v
Or directly: python tests/test_debater.py
"""
from agents.debater import debate1_A, debate1_B, build_debate1_prompt_A, build_debate1_prompt_B

# ── Shared test states ────────────────────────────────────────────────────────

BASE_STATE = {
    "raw_input": "Build a real-time chat app in 3 weeks with 2 developers",
    "project_context": {
        "goal": "real-time chat app",
        "timeline": "3 weeks",
        "team_size": 2,
        "constraints": [],
        "stack": None,
        "methodology": None,
    },
    "user_provided_fields": {
        "goal": True,
        "timeline": True,
        "team_size": True,
        "stack": False,
        "methodology": False,
    },
    "debate1_arguments": [],
    "debate1_rounds": 1,
}

USER_STACK_STATE = {
    **BASE_STATE,
    "project_context": {**BASE_STATE["project_context"], "stack": "Firebase"},
    "user_provided_fields": {**BASE_STATE["user_provided_fields"], "stack": True},
}

ROUND2_STATE = {
    **BASE_STATE,
    "debate1_rounds": 2,
    "debate1_arguments": [
        {"agent": "A", "argument": "I propose React + Node.js + Socket.io for real-time capabilities.", "round": 1},
        {"agent": "B", "argument": "Firebase is simpler and handles real-time out of the box.", "round": 1},
    ],
}


# ── Prompt tests (no LLM call) ────────────────────────────────────────────────

def test_prompt_A_contains_project_info():
    prompt = build_debate1_prompt_A(BASE_STATE)
    assert "real-time chat app" in prompt
    assert "3 weeks" in prompt
    assert "2" in prompt
    print("✅ Prompt A contains project info")

def test_prompt_A_free_stack():
    prompt = build_debate1_prompt_A(BASE_STATE)
    assert "Propose the best tech stack" in prompt
    assert "user has already specified" not in prompt
    print("✅ Prompt A proposes stack freely when user didn't specify one")

def test_prompt_A_user_stack():
    prompt = build_debate1_prompt_A(USER_STACK_STATE)
    assert "Firebase" in prompt
    assert "Validate whether" in prompt
    print("✅ Prompt A validates user stack instead of proposing freely")

def test_prompt_A_round2_includes_B_argument():
    prompt = build_debate1_prompt_A(ROUND2_STATE)
    assert "round 2" in prompt.lower() or "round2" in prompt.lower() or "previous round" in prompt.lower()
    assert "Firebase" in prompt  # B's argument from round 1
    print("✅ Prompt A in round 2 includes B's previous argument")

def test_prompt_B_includes_A_argument():
    state_with_A = {
        **BASE_STATE,
        "debate1_arguments": [
            {"agent": "A", "argument": "I propose React + Node.js + Socket.io.", "round": 1}
        ],
    }
    prompt = build_debate1_prompt_B(state_with_A)
    assert "React + Node.js + Socket.io" in prompt
    print("✅ Prompt B includes Agent A's argument")

def test_prompt_B_honest_assessment():
    prompt = build_debate1_prompt_B(BASE_STATE)
    assert "honest assessment" in prompt or "independently analyse" in prompt
    assert "challenge, stress-test" not in prompt
    print("✅ Prompt B asks for honest assessment, not forced challenge")


# ── Live LLM tests (call Groq API) ───────────────────────────────────────────

def test_debate1_A_live():
    result = debate1_A(BASE_STATE)

    assert "debate1_arguments" in result
    assert len(result["debate1_arguments"]) == 1
    arg = result["debate1_arguments"][0]
    assert arg["agent"] == "A"
    assert arg["round"] == 1
    assert len(arg["argument"]) > 20  # not empty
    assert result["debate1_rounds"] == 1  # A does not increment rounds
    assert result["current_node"] == "debate1_A"

    print(f"✅ debate1_A responded ({len(arg['argument'])} chars):")
    print(f"   {arg['argument'][:200]}...")

def test_debate1_B_after_A():
    # Simulate A having already argued
    state_after_A = {
        **BASE_STATE,
        "debate1_arguments": [
            {"agent": "A", "argument": "I propose React + Node.js + Socket.io for real-time. It gives full control over WebSocket connections and scales well with 2 devs.", "round": 1}
        ],
    }

    result = debate1_B(state_after_A)

    assert "debate1_arguments" in result
    assert len(result["debate1_arguments"]) == 2  # A + B
    arg = result["debate1_arguments"][-1]
    assert arg["agent"] == "B"
    assert arg["round"] == 1
    assert len(arg["argument"]) > 20
    assert result["debate1_rounds"] == 2  # B increments to signal round complete
    assert result["current_node"] == "debate1_B"

    print(f"✅ debate1_B responded ({len(arg['argument'])} chars):")
    print(f"   {arg['argument'][:200]}...")

def test_full_round1():
    """Simulate a complete round 1: A argues, then B responds."""
    print("\n── Full Round 1 ──────────────────────────────")

    result_A = debate1_A(BASE_STATE)
    print(f"Agent A: {result_A['debate1_arguments'][-1]['argument']}\n")

    state_after_A = {**BASE_STATE, "debate1_arguments": result_A["debate1_arguments"]}
    result_B = debate1_B(state_after_A)
    print(f"Agent B: {result_B['debate1_arguments'][-1]['argument']}\n")

    assert len(result_B["debate1_arguments"]) == 2
    assert result_B["debate1_rounds"] == 2
    print("✅ Full round 1 completed successfully")

def test_full_round2():
    """Simulate round 2: agents refine their positions."""
    print("\n── Full Round 2 ──────────────────────────────")

    result_A2 = debate1_A(ROUND2_STATE)
    print(f"Agent A (round 2): {result_A2['debate1_arguments'][-1]['argument']}\n")

    state_after_A2 = {**ROUND2_STATE, "debate1_arguments": result_A2["debate1_arguments"]}
    result_B2 = debate1_B(state_after_A2)
    print(f"Agent B (round 2): {result_B2['debate1_arguments'][-1]['argument']}\n")

    assert result_B2["debate1_rounds"] == 3
    print("✅ Full round 2 completed successfully")


if __name__ == "__main__":
    print("═" * 60)
    print("PROMPT TESTS (no LLM)")
    print("═" * 60)
    test_prompt_A_contains_project_info()
    test_prompt_A_free_stack()
    test_prompt_A_user_stack()
    test_prompt_A_round2_includes_B_argument()
    test_prompt_B_includes_A_argument()
    test_prompt_B_honest_assessment()

    print("\n" + "═" * 60)
    print("LIVE LLM TESTS (calls Groq API)")
    print("═" * 60)
    test_debate1_A_live()
    test_debate1_B_after_A()
    test_full_round1()
    test_full_round2()

    print("\n" + "═" * 60)
    print("ALL TESTS PASSED ✅")
    print("═" * 60)