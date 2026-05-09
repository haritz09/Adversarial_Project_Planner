# agents/debater.py
import json
import re
import os
from langchain_groq import ChatGroq
from graph.state import DebateState
from dotenv import load_dotenv

load_dotenv()


def get_llm() -> ChatGroq:
    return ChatGroq(model="llama-3.1-8b-instant")

llm_debater = get_llm()

def build_debate1_prompt_A(state: DebateState) -> str:
    ctx = state["project_context"]
    provided = state.get("user_provided_fields", {})
    previous_args = state.get("debate1_arguments", [])
    current_round = state.get("debate1_rounds", 1)

    project_info = f"""
        Project goal: {ctx.get("goal", "not specified")}
        Timeline: {ctx.get("timeline", "not specified")}
        Team size: {ctx.get("team_size", "not specified")}
        Constraints: {", ".join(ctx.get("constraints", [])) or "none"}
    """

    # If user already specified a stack, agents validate instead of proposing freely
    stack_instruction = ""
    if provided.get("stack") and ctx.get("stack"):
        stack_instruction = f"""
            The user has already specified they want to use: {ctx["stack"]}.
            Do NOT argue against this choice. Instead:
            - Validate whether it is a good fit for this project
            - Identify potential risks or limitations with this stack
            - Suggest complementary tools or improvements
        """
    else:
        stack_instruction = """
            Propose the best tech stack for this project.
            Consider: scalability needs, team size, timeline constraints, and long-term maintainability.
        """

    # If this is round 2+, acknowledge previous arguments
    previous_context = ""
    if current_round > 1 and previous_args:
        last_b_args = [a for a in previous_args if a["agent"] == "B"]
        if last_b_args:
            last_b = last_b_args[-1]["argument"]
            previous_context = f"""
                This is round {current_round}. In the previous round, Agent B argued:
                \"{last_b}\"

                Refine or defend your position taking their argument into account.
            """

    return f"""
        You are Agent A in a technical debate about the best stack for a software project.
        Your role is to propose and defend a concrete technical approach.
        Be specific, concise, and grounded in the project constraints.

        PROJECT CONTEXT:
        {project_info}
        {stack_instruction}
        {previous_context}
        Respond in 3-5 sentences maximum. Be direct and specific — no generic advice.
    """


def build_debate1_prompt_B(state: DebateState) -> str:
    ctx = state["project_context"]
    provided = state.get("user_provided_fields", {})
    previous_args = state.get("debate1_arguments", [])
    current_round = state.get("debate1_rounds", 1)

    # Base project context
    project_info = f"""
        Project goal: {ctx.get("goal", "not specified")}
        Timeline: {ctx.get("timeline", "not specified")}
        Team size: {ctx.get("team_size", "not specified")}
        Constraints: {", ".join(ctx.get("constraints", [])) or "none"}
    """

    # Get Agent A's latest argument — B always responds to A
    last_a_args = [a for a in previous_args if a["agent"] == "A"]
    if last_a_args:
        agent_a_argument = last_a_args[-1]["argument"]
        a_context = f"""
            Agent A has proposed the following:
            \"{agent_a_argument}\"

            Your job is to challenge this proposal. You can:
            - Disagree and propose a completely different stack
            - Partially agree but highlight critical flaws or risks
            - Accept parts of the proposal but argue for key modifications
        """
    else:
        # Fallback — should not happen in normal flow
        a_context = "Propose an alternative tech stack to what Agent A might suggest."

    # If user already specified a stack, B challenges or validates it differently
    stack_instruction = ""
    if provided.get("stack") and ctx.get("stack"):
        stack_instruction = f"""
            The user has specified they want to use: {ctx["stack"]}.
            Agent A has already analysed this choice. Your role is to independently evaluate it:
            - Analyse whether this stack is genuinely a good fit for this specific project
            - If you agree with Agent A, explain why and add any relevant considerations they missed
            - If you see real risks or a better alternative, argue for it with concrete reasoning
            Be honest — do not challenge for the sake of it, but do not agree without analysis either.
        """
    else:
        stack_instruction = """
            Propose a concrete alternative stack or challenge Agent A's reasoning directly.
            Do not simply agree — your role is to stress-test their proposal.
        """

    # Round 2+ — B refines based on A's updated position
    previous_context = ""
    if current_round > 1:
        last_a_prev = [a for a in previous_args if a["agent"] == "A" and a["round"] < current_round]
        if last_a_prev:
            previous_context = f"""
                This is round {current_round}. You have already argued before.
                Agent A has refined their position — respond to their updated argument specifically.
                Avoid repeating points you already made in previous rounds.
            """

    return f"""
        You are Agent B in a technical debate about the best stack for a software project.
        Your role is to independently analyse Agent A's proposal and respond with your honest assessment.
        Be specific, rigorous, and grounded in the project constraints.
        You may agree, partially agree, or disagree — but always justify your position with concrete reasoning

        PROJECT CONTEXT:
        {project_info}
        {a_context}
        {stack_instruction}
        {previous_context}
        Respond in 3-5 sentences maximum. Be direct and specific — no generic advice.
    """


def debate1_A(state: DebateState) -> dict:
    prompt = build_debate1_prompt_A(state)
    response = llm_debater.invoke(prompt)
    
    argument = response.content if hasattr(response, "content") else str(response)
    current_round = state.get("debate1_rounds", 1)
    previous_args = state.get("debate1_arguments", [])

    return {
        "debate1_arguments": previous_args + [{"agent": "A", "argument": argument, "round": current_round}],
        "debate1_rounds": current_round,
        "current_node": "debate1_A",
    }


def debate1_B(state: DebateState) -> dict:
    prompt = build_debate1_prompt_B(state)
    response = llm_debater.invoke(prompt)

    argument = response.content if hasattr(response, "content") else str(response)
    current_round = state.get("debate1_rounds", 1)
    previous_args = state.get("debate1_arguments", [])

    return {
        "debate1_arguments": previous_args + [{"agent": "B", "argument": argument, "round": current_round}],
        "debate1_rounds": current_round + 1,    # Round increases when B finishes
        "current_node": "debate1_B",
    }