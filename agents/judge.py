import json
import re 
from langchain_groq import ChatGroq
from langgraph.types import interrupt
from graph.state import DebateState
from dotenv import load_dotenv

load_dotenv()

llm_judge = ChatGroq(model="llama-3.1-8b-instant")

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
 
    return f"""
        You are an impartial and critical technical judge evaluating a debate about the best tech stack for a software project.
        
        PROJECT CONTEXT:
        {project_info}
        
        DEBATE HISTORY:
        {debate_history}
        
        Your task:
        1. Evaluate the quality of each agent's arguments across all rounds being critical and do not hesitate on calling out incorrect arguments.
        2. Decide if the debate has reached a clear enough conclusion or needs another round
        3. If concluding: pick the winning position and explain why it best fits the project
        
        Evaluate each agent on:
        - Specificity: are they proposing concrete technologies, not vague concepts?
        - Relevance: does their proposal fit the timeline, team size, and constraints?
        - Soundness: is their reasoning logically coherent?
        
        Respond ONLY with a JSON object in this exact format:
        {{
            "needs_another_round": true or false,
            "reason_for_continuing": "only if needs_another_round is true, explain what is still unresolved",
            "winner": "A" or "B" or "tie" (never null or empty),
            "winning_stack": "the concrete stack chosen e.g. React + Node.js + PostgreSQL" (never null or empty),
            "rationale": "2-3 sentences explaining the decision" (only if needs_another_round is false),
            "agent_a_score": a number from 0 to 10,
            "agent_b_score": a number from 0 to 10
        }}
        
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
 
    # Force conclusion if max rounds reached — no need to call the LLM
    if current_round > MAX_ROUNDS:
        arguments = state.get("debate1_arguments", [])
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
 
    return {
        "debate1_decision": decision.get("winning_stack", "undetermined"),
        "debate1_judge_rationale": decision.get("rationale") or decision.get("reason_for_continuing", ""),
        "debate1_winner": decision.get("winner") or "tie",
        "debate1_winning_stack": decision.get("winning_stack") or "undetermined",
        "debate1_winning_stack": decision.get("winning_stack", ""),
        "debate1_needs_another_round": needs_another_round,
        "debate1_agent_a_score": decision.get("agent_a_score", 5),
        "debate1_agent_b_score": decision.get("agent_b_score", 5),
        "current_node": "debate1_judge",
    }


def _extract_best_stack(arguments: list[dict]) -> str:
    """Fallback: extract a stack from the last argument when max rounds are reached."""
    if not arguments:
        return "undetermined"
    last = arguments[-1]["argument"]
    return last[:200] + "..." if len(last) > 200 else last


# Conditional edge
def should_continue_debate1(state: DebateState) -> str:
    """
    Conditional edge function called after debate1_judge.
    Returns the name of the next node.
    """
    if state.get("debate1_needs_another_round", False):
        return "debate1_A"
    return "architecture_generator"