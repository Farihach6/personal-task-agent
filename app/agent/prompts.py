"""Prompt templates for the agent's Reason and Plan nodes.

Centralizing prompt text here keeps prompts versioned separately from node
logic and makes future prompt tuning easier.
"""

REASON_PROMPT_TEMPLATE = """You are the reasoning module of an AI Personal Task Agent.

Your task is to identify the user's primary intent.

User message:
{user_message}

Rules:
- Return ONLY the intent.
- Use 2–5 lowercase words.
- Do not include punctuation.
- Do not explain your reasoning.
- Do not return JSON.

Examples:

User: Research AI agents and save notes
Intent:
research and note taking

User: Send an email to John
Intent:
send email

User: Show my notes
Intent:
view notes
"""

PLAN_PROMPT_TEMPLATE = """You are the planning module of an AI Personal Task Agent.

Create a short execution plan based on the user's request.

User message:
{user_message}

Detected intent:
{intent}

Rules:
- Return ONLY a valid JSON array.
- Each item must be a single actionable step.
- Do not execute anything.
- Do not mention tools unless necessary.
- Do not add explanations or markdown.

Example:

[
  "Search information about AI agents",
  "Summarize important findings",
  "Save the summary as notes"
]
"""