from typing import TypedDict

class Risk(TypedDict):
    description: str
    probability: str     # "Low" | "Medium" | "High"
    impact: str          # "Low" | "Medium" | "High"
    mitigation: str
    action_plan: str

class Milestone(TypedDict):
    name: str
    target_date: str     # "YYYY-MM-DD"
    description: str

class Phase(TypedDict):
    name: str
    tasks: list[str]
    duration_range: str  # "3-5 days"

class TaskEstimate(TypedDict):
    task: str
    effort_range: str    # "2-4h"
    phase: str

class Requirement(TypedDict):
    description: str
    priority: str        # "Must" | "Should" | "Could"
    type: str           # func | non-func

class AcceptanceCriterion(TypedDict):
    feature: str
    criteria: list[str]