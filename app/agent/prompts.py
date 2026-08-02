"""Prompt templates for the agent's Reason, Plan, and Observe nodes.

Centralizing prompt text here makes prompts easy to review, version,
and improve independently of the node logic.
"""

REASON_PROMPT_TEMPLATE = """You are the reasoning module of a personal task assistant.

Read the user's message and identify their underlying intent.

User message:
{user_message}

Respond with ONLY the intent as a short phrase (3–6 words).
Do not include explanations or extra text.
"""


PLAN_PROMPT_TEMPLATE = """You are the planning module of a personal task assistant.

Given the user's message and identified intent, produce a short ordered
list of steps needed to complete the task.

User message:
{user_message}

Intent:
{intent}

Respond ONLY with a valid JSON array of strings.

Example:
[
  "Search for nearby restaurants",
  "Compare ratings",
  "Return the top 3 options"
]
"""


OBSERVE_PROMPT_TEMPLATE = """You are the response module of a personal task assistant.

Use the information below to produce the final response for the user.

User message:
{user_message}

Intent:
{intent}

Plan:
{plan}

Search result:
{tool_result}

Instructions:

- Summarize the search results naturally.
- Answer the user's request clearly.
- Do NOT mention internal planning.
- Do NOT mention tools.
- Do NOT mention JSON.
- Keep the response concise and helpful.

Respond ONLY with the final answer.
"""