import json
import re 
from langchain_groq import ChatGroq
from langgraph.types import interrupt
from graph.state import DebateState
from dotenv import load_dotenv

load_dotenv()

llm_judge = ChatGroq(model="llama-3.3-70b-versatile")

MIN_ROUNDS= 2
MAX_ROUNDS = 3

def build_judge_prompt(state: DebateState) -> str:
    ctx = state['project_context']
    arguments = state.get("debate1_arguments", [])
    current_round = state.get("debate1_rounds", 1)

    project_info = f"""
        Project goal: {ctx.get("goal", "not specified")}
        Timeline: {ctx.get("timeline", "not specified")}
        Team size: {ctx.get("team_size", "not specified")}
        Constraints: {", ".join(ctx.get("constraints", [])) or "none"}
    """
 
    # Format debate history grouped by round
    debate_history = ""
    rounds = sorted(set(a["round"] for a in arguments))
    for r in rounds:
        round_args = [a for a in arguments if a["round"] == r]
        debate_history += f"\n--- Round {r} ---\n"
        for arg in round_args:
            debate_history += f"Agent {arg['agent']}: {arg['argument']}\n"
            
    final_round_warning = ""
    if current_round >= MAX_ROUNDS:
        final_round_warning = """
        CRITICAL: This is the FINAL round allowed. 
        You MUST conclude the debate (needs_another_round: false).
        You MUST declare a clear winner ("A" or "B") and a winning_stack. Do not ask for another round!
        """
 
    continuation_instructions = ""
    if not final_round_warning:
        continuation_instructions = """
        Request another round (needs_another_round: true) if ANY of these apply:
        - An agent made a claim without concrete evidence or specific technology names
        - A direct question or challenge from one agent was not addressed by the other
        - Arguments are generic and not grounded in THIS project's specific constraints
        - The disagreement is still fundamental and unresolved
        - One agent proposed an alternative but did not justify it against the project constraints
        - You need one agent to respond directly to the other's strongest point
        """
 
    return f"""
        You are an impartial and critical technical judge evaluating a debate about the best tech stack for a software project.
        
        PROJECT CONTEXT:
        {project_info}
        
        DEBATE HISTORY:
        {debate_history}
        {final_round_warning}
        
        {continuation_instructions}

        Conclude (needs_another_round: false) if any of these are true:
        - Both agents have argued with concrete, project-specific evidence
        - The stronger position is clearly justified based on the constraints
        - Further debate would not change the outcome
        - { "THIS IS THE FINAL ROUND, YOU MUST CONCLUDE" if final_round_warning else "" }

        A "tie" is only valid if both positions are genuinely equal after full analysis.
        Calling a tie to avoid deciding is NOT acceptable.
        
        Respond ONLY with a JSON object in this exact format:
        {{
            "needs_another_round": true or false,
            "reason_for_continuing": "if needs_another_round is true, explain what is still unresolved",
            "winner": "A" or "B",
            "winning_stack": "the concrete stack chosen e.g. React + Node.js + PostgreSQL",
            "rationale": "2-3 sentences explaining why A or B won",
            "agent_a_score": a number from 0 to 10,
            "agent_b_score": a number from 0 to 10
        }}
        
        CRITICAL: 
        - DO NOT use "N/A", "null", or "none" for winner or winning_stack if needs_another_round is false.
        - You ARE the decision maker. Pick the strongest argument.
        
        Return ONLY the JSON object. No explanation, no markdown, no code fences.
    """
    
def parse_judge_response(text: str) -> dict:
    """Parse LLM response to JSON with tolerant fallback."""
    if not isinstance(text, str):
        text = str(text)
 
    try:
        return json.loads(text)
    except Exception:
        pass
 
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    # Final fallback — force conclusion to avoid infinite loop
    return {
        "needs_another_round": False,
        "winner": "tie",
        "winning_stack": "undetermined",
        "rationale": "Judge could not parse a clear decision from the debate.",
        "agent_a_score": 5,
        "agent_b_score": 5,
    }


def debate1_judge(state: DebateState) -> dict:
    """
    Evaluates the debate so far and decides:
    - needs_another_round: True → loop back to debate1_A
    - needs_another_round: False → continue to architecture_generator
    
    Also populates debate1_decision and debate1_judge_rationale in the state.
    """
    current_round = state.get("debate1_rounds", 1)
    arguments = state.get("debate1_arguments", [])
 
    # Force conclusion if max rounds reached — no need to call the LLM
    if current_round > MAX_ROUNDS:
        return {
            "debate1_decision": "max_rounds_reached",
            "debate1_judge_rationale": f"Maximum rounds ({MAX_ROUNDS}) reached. Concluding debate based on arguments so far.",
            "debate1_winner": "tie",
            "debate1_winning_stack": _extract_best_stack(arguments),
            "debate1_needs_another_round": False,
            "current_node": "debate1_judge",
        }
 
    prompt = build_judge_prompt(state)
    response = llm_judge.invoke(prompt)
    text = response.content if hasattr(response, "content") else str(response)
    decision = parse_judge_response(text)
 
    needs_another_round = decision.get("needs_another_round", False)
 
    # Never allow more rounds than MAX_ROUNDS
    if current_round >= MAX_ROUNDS:
        needs_another_round = False
        
    winner = decision.get("winner")
    if not winner or winner.upper() in ["N/A", "NULL", "NONE"]:
        winner = "tie"
        
    stack = decision.get("winning_stack")
    if not stack or stack.upper() in ["N/A", "NULL", "NONE", "UNDETERMINED"]:
        stack = _extract_best_stack(arguments)
 
    return {
        "debate1_decision": stack,
        "debate1_judge_rationale": decision.get("rationale") or decision.get("reason_for_continuing", ""),
        "debate1_winner": winner,
        "debate1_winning_stack": stack,
        "debate1_needs_another_round": needs_another_round,
        "debate1_judge_continue_reason": decision.get("reason_for_continuing", ""),
        "debate1_agent_a_score": decision.get("agent_a_score", 5),
        "debate1_agent_b_score": decision.get("agent_b_score", 5),
    }


def _extract_best_stack(arguments: list[dict]) -> str:
    """Fallback: extract a stack from the last argument when max rounds are reached."""
    if not arguments:
        return "undetermined"
    last = arguments[-1]["argument"]
    return last[:200] + "..." if len(last) > 200 else last


# Conditional edge
def should_continue_debate1(state: DebateState) -> list[str]:
    """
    Conditional edge function called after debate1_judge.
    Returns a list of nodes to execute next.
    """
    current_round = state.get("debate1_rounds", 1)
    if current_round < MIN_ROUNDS:
        return ["debate1_A"]
    if state.get("debate1_needs_another_round", False):
        return ["debate1_A"]
    return ["architecture_generator", "debate_flow_generator"]