Extract the following fields from the project description as a JSON object.
If a field is not mentioned, set it to null.

Fields:
- goal: what the project builds (string)
- timeline: how long it takes (string, e.g. "3 weeks", "2 months")
- team_size: number of developers (integer or null)
- constraints: list of explicit constraints mentioned (list of strings, empty list if none)
- stack: technology stack if explicitly mentioned (string or null)
- methodology: delivery approach if explicitly mentioned, e.g. "scrum", "kanban" (string or null)

Example output:
{{"goal": "real-time chat app", "timeline": "3 weeks", "team_size": 2, "constraints": ["must use existing auth system"], "stack": "Firebase", "methodology": null}}

Project description:
{raw_input}

Return ONLY the JSON object. No explanation, no markdown, no code fences.
