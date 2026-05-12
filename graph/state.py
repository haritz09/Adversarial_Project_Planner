from typing import TypedDict
from graph.output_types import (
    Risk, Milestone, Phase,
    TaskEstimate, Requirement, AcceptanceCriterion
)


class DebateState(TypedDict):
    # Input
    raw_input: str
    project_context: dict          # {goal, timeline, team_size, constraints, stack?}
    user_provided_fields: dict | None   # {stack: True, timeline: False, ...}

    # Debate 1 — Tech Stack
    debate1_arguments: list[dict]  # [{agent, argument, round}]
    debate1_rounds: int
    debate1_decision: str
    debate1_skipped: bool          # True if the user already specified the stack
    debate1_needs_another_round: bool
    debate1_judge_continue_reason: str | None
    debate1_judge_rationale: str | None 

    # Narrative documents (Markdown strings)
    architecture_doc: str          # components and key decisions
    scope_doc: str                 # MVP, objectives, out-of-scope
    techstack_doc: str             # chosen stack + debate justification
    timeline_doc: str              # contains Mermaid Gantt + WBS blocks
    debate_flow_doc: str           # full debate transcript + judge decision

    # Structured documents (lists of TypedDicts → Notion tables/checklists)
    requirements_doc: list[Requirement]
    risks_doc: list[Risk]
    phases_doc: list[Phase]
    estimates_doc: list[TaskEstimate]
    milestones_doc: list[Milestone]
    acceptance_doc: list[AcceptanceCriterion]

    # Notion
    notion_parent_page_id: str     # from .env
    notion_urls: dict              # {root, architecture, requirements, ...}
    notion_page_ids: dict | None   # {root, architecture, plan} - store created page IDs

    # Tracing and metadata
    langfuse_session_id: str | None
    trace_ids: dict | None         # {debate1, judge1, architecture_gen}
    current_node: str | None       # e.g., 'intake', 'debate1', 'judge', 'plan_generated', 'notion_written', 'done'
    created_at: str | None
    updated_at: str | None
    run_id: str | None
    max_rounds: int | None

    # Compact plan output for single-page MVP
    project_plan_doc: str | None    