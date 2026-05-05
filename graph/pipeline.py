from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import DebateState
from agents.intake import intake_node

builder = StateGraph(DebateState)
def debate1_A(state: DebateState) -> dict:
	return {"debate1_arguments": state.get("debate1_arguments", []) + [{"agent": "A", "argument": "(placeholder)", "round": 1}], "current_node": "debate1_A"}


def debate1_B(state: DebateState) -> dict:
	return {"debate1_arguments": state.get("debate1_arguments", []) + [{"agent": "B", "argument": "(placeholder)", "round": 1}], "current_node": "debate1_B"}


def debate1_judge(state: DebateState) -> dict:
	return {"debate1_decision": "choose_stack_placeholder", "debate1_judge_rationale": "(placeholder rationale)", "current_node": "debate1_judge"}


def architecture_generator(state: DebateState) -> dict:
	return {"architecture_doc": "# Architecture\n(placeholder)\n", "current_node": "architecture_generator"}


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


def plan_generator(state: DebateState) -> dict:
	# Compose a compact project plan for MVP
	plan_md = "# Project Plan\n- Phase 1: MVP (placeholder)\n"
	return {"project_plan_doc": plan_md, "current_node": "plan_generator"}


def notion_writer(state: DebateState) -> dict:
	# In production this will call Notion MCP and create pages sequentially.
	# Here we record placeholder page IDs and URLs.
	root_id = state.get("notion_parent_page_id") or "NOTION_PARENT_PLACEHOLDER"
	page_ids = {"root": root_id, "architecture": f"{root_id}-arch", "plan": f"{root_id}-plan"}
	urls = {k: f"https://notion.fake/{v}" for k, v in page_ids.items()}
	return {"notion_page_ids": page_ids, "notion_urls": urls, "current_node": "notion_writer"}


# --- Build graph nodes and edges following AGENT_CONTEXT.md order ---
builder.add_node(intake_node)
builder.add_edge(START, "intake_node")

builder.add_node(debate1_A)
builder.add_node(debate1_B)
builder.add_node(debate1_judge)
builder.add_node(architecture_generator)

# Debate 2 always runs (do not skip)
builder.add_node(debate2_A)
builder.add_node(debate2_B)
builder.add_node(debate2_judge)

builder.add_node(requirements_generator)
builder.add_node(plan_generator)
builder.add_node(notion_writer)

# Linear edges following the pipeline; using explicit ordering ensures debate2 always executes
builder.add_edge("intake_node", "debate1_A")
builder.add_edge("debate1_A", "debate1_B")
builder.add_edge("debate1_B", "debate1_judge")
builder.add_edge("debate1_judge", "architecture_generator")
builder.add_edge("architecture_generator", "debate2_A")
builder.add_edge("debate2_A", "debate2_B")
builder.add_edge("debate2_B", "debate2_judge")
builder.add_edge("debate2_judge", "requirements_generator")
builder.add_edge("requirements_generator", "plan_generator")
builder.add_edge("plan_generator", "notion_writer")
builder.set_finish_point("notion_writer")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)