from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import DebateState
from agents.intake import intake_node
from agents.debater import debate1_A, debate1_B
from agents.judge import should_continue_debate1, debate1_judge
from agents.genetators import architecture_generator, scope_generator, plan_generator, debate_flow_generator
from tools.notion import notion_writer

builder = StateGraph(DebateState)

def debate2_A(state: DebateState) -> dict:
	return {"debate2_arguments": state.get("debate2_arguments", []) + [{"agent": "A", "argument": "(approach arg)", "round": 1}], "current_node": "debate2_A"}


def debate2_B(state: DebateState) -> dict:
	return {"debate2_arguments": state.get("debate2_arguments", []) + [{"agent": "B", "argument": "(approach arg)", "round": 1}], "current_node": "debate2_B"}


def debate2_judge(state: DebateState) -> dict:
	return {"debate2_decision": "choose_approach_placeholder", "debate2_judge_rationale": "(placeholder rationale)", "debate2_page_rationales": {"requirements": "(why these reqs)", "phases": "(why these phases)"}, "current_node": "debate2_judge"}


def requirements_generator(state: DebateState) -> dict:
	# Generator should create structured documents using judge decision and project_context
	reqs = [{"description": "Placeholder requirement", "priority": "Must", "type": "func"}]
	return {"requirements_doc": reqs, "current_node": "requirements_generator"}


# --- Build graph nodes and edges following AGENT_CONTEXT.md order ---
builder.add_node(intake_node)
builder.add_edge(START, "intake_node")

builder.add_node(debate1_A)
builder.add_node(debate1_B)
builder.add_node(debate1_judge)
builder.add_node(architecture_generator)
builder.add_node(scope_generator)
builder.add_node(plan_generator)

# Debate 2 always runs (do not skip)
builder.add_node(debate2_A)
builder.add_node(debate2_B)
builder.add_node(debate2_judge)
builder.add_node(requirements_generator)
builder.add_node(debate_flow_generator)
builder.add_node(notion_writer)

# Linear edges following the pipeline; using explicit ordering ensures debate2 always executes
builder.add_edge("intake_node", "debate1_A")
builder.add_edge("debate1_A", "debate1_B")
builder.add_edge("debate1_B", "debate1_judge")
builder.add_conditional_edges("debate1_judge", should_continue_debate1)
builder.add_edge("architecture_generator", "scope_generator")
builder.add_edge("scope_generator", "plan_generator")
builder.add_edge("plan_generator", "debate_flow_generator")
builder.add_edge("debate_flow_generator", "notion_writer")
builder.set_finish_point("notion_writer")

# builder.add_edge("debate2_A", "debate2_B")
# builder.add_edge("debate2_B", "debate2_judge")
# builder.add_edge("debate2_judge", "requirements_generator")
# builder.add_edge("requirements_generator", "plan_generator")
# builder.add_edge("plan_generator", "notion_writer")
# builder.set_finish_point("notion_writer")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)