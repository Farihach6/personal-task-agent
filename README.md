# Personal Task Agent

An AI-powered personal task agent that understands natural-language requests and autonomously completes multi-step tasks using a **Reason → Plan → Act → Observe** workflow.

The project is built with **FastAPI, LangGraph, Groq, SQLAlchemy, SQLite, Pydantic, and vanilla HTML/CSS/JavaScript**. It combines AI reasoning with practical tools, human approval, workflow persistence, execution logging, guardrails, and a web dashboard.

---

## 🚀 Project Overview

The Personal Task Agent is designed to behave like an intelligent assistant that can take a user's natural-language request, reason about it, create an execution plan, use appropriate tools, observe their results, and produce a final response.

The core workflow is:

```text
User Request
     │
     ▼
┌─────────────┐
│   Reason    │
└──────┬──────┘
       ▼
┌─────────────┐
│    Plan     │
└──────┬──────┘
       ▼
┌─────────────┐
│     Act     │
└──────┬──────┘
       ▼
┌─────────────┐
│   Observe   │
└──────┬──────┘
       │
       ├──────► More steps required
       │              │
       │              └──────► Plan / Act / Observe
       │
       ▼
┌─────────────────┐
│ Final Response  │
└─────────────────┘
```

For actions that require human authorization, the workflow can pause and wait for approval before continuing.

---

# ✨ Features

## 🤖 AI Agent

* Natural-language task understanding
* LLM-powered reasoning
* Structured planning
* Multi-step task execution
* Reason → Plan → Act → Observe workflow
* LangGraph-based state management
* Configurable maximum agent steps
* Final response generation

## 🧠 Agent Tools

The agent can work with multiple tools, including:

* 🔎 **Search Tool**

  * Performs research/search operations
  * Returns information to the agent for observation

* 📝 **Notes Tool**

  * Creates and manages notes
  * Persists notes in SQLite

* 📧 **Email Tool**

  * Prepares and sends emails
  * Supports human approval before sending

* 🛠️ **Tool Executor**

  * Centralized tool dispatching
  * Routes tool calls to the appropriate implementation

## 👤 Human Approval

Potentially sensitive actions can require explicit human approval.

For example:

```text
Agent
  │
  ▼
Create Email
  │
  ▼
Requires Approval?
  │
  ├── No ──────► Send Email
  │
  └── Yes
       │
       ▼
   Pause Workflow
       │
       ▼
 Human Approval
       │
       ├── Approved ──► Continue
       │
       └── Rejected ──► Stop / Handle Rejection
```

This prevents the agent from performing selected actions without user authorization.

---

# 📊 Dashboard

The application includes a browser-based dashboard built with vanilla HTML, CSS, and JavaScript.

The dashboard provides separate sections for:

* 💬 Chat
* 📜 Workflow History
* 📝 Notes
* 📋 Execution Logs

The dashboard communicates with the FastAPI backend through REST APIs.

---

# 📜 Workflow History

The system persists workflow execution history in the database.

Each workflow can contain multiple execution steps.

Supported workflow information includes:

* Workflow ID
* User request
* Workflow status
* Start time
* Completion time
* Failure information
* Individual workflow steps
* Step types
* Step status
* Tool name
* Step input/output information

The workflow history dashboard allows previous executions to be inspected after they have completed.

---

# 📋 Execution Logs

The project includes a centralized execution logging system.

The `LoggingService` records important agent events both to:

1. The Python application logger
2. The `execution_logs` database table

Execution logs can be associated with a workflow and queried through the logging API.

The logging system is integrated into the major agent nodes:

* Reason
* Plan
* Act
* Observe

This provides visibility into what the agent was doing during execution.

Example execution flow:

```text
Workflow Started
      │
      ▼
Reason Node
      │
      ▼
Plan Node
      │
      ▼
Act Node
      │
      ▼
Observe Node
      │
      ▼
Tool Result
      │
      ▼
Next Step / Final Response
```

The Execution Logs Dashboard provides a centralized view of these events.

---

# 🗄️ Persistence

The application uses:

* SQLite
* SQLAlchemy ORM

Persistent data includes:

* Notes
* Workflows
* Workflow steps
* Execution logs

The database location is configurable through the environment configuration.

SQLite tables are initialized automatically when the application starts.

---

# 🏗️ Architecture

The project follows a layered architecture.

```text
┌──────────────────────────────────────────┐
│              Frontend Dashboard          │
│        HTML / CSS / Vanilla JS           │
└─────────────────────┬────────────────────┘
                      │ HTTP / REST
                      ▼
┌──────────────────────────────────────────┐
│               FastAPI API                │
│      Routes / Validation / DI             │
└─────────────────────┬────────────────────┘
                      ▼
┌──────────────────────────────────────────┐
│                Services                  │
│ AgentService / WorkflowService /         │
│ LoggingService / EmailService             │
└─────────────────────┬────────────────────┘
                      ▼
┌──────────────────────────────────────────┐
│              LangGraph Agent             │
│                                          │
│ Reason → Plan → Act → Observe            │
└───────────┬──────────────────┬───────────┘
            │                  │
            ▼                  ▼
      Agent Tools          Groq LLM
            │
            ▼
┌──────────────────────────────────────────┐
│             Database Layer               │
│       SQLAlchemy + SQLite                │
└──────────────────────────────────────────┘
```

---

# 📁 Project Structure

```text
personal-task-agent/
│
├── app/
│   ├── agent/
│   │   ├── nodes/
│   │   │   ├── reason.py
│   │   │   ├── plan.py
│   │   │   ├── act.py
│   │   │   └── observe.py
│   │   │
│   │   ├── tools/
│   │   │   ├── search_tool.py
│   │   │   ├── notes_tool.py
│   │   │   ├── email_tool.py
│   │   │   └── tool_executor.py
│   │   │
│   │   ├── graph.py
│   │   └── state.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── notes.py
│   │   │   ├── workflows.py
│   │   │   ├── logs.py
│   │   │   └── approvals.py
│   │   │
│   │   └── dependencies.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   │
│   ├── database/
│   │   ├── engine.py
│   │   ├── repositories/
│   │   └── init_db.py
│   │
│   ├── models/
│   │   ├── workflow.py
│   │   ├── note.py
│   │   └── execution_log.py
│   │
│   ├── schemas/
│   │   ├── agent.py
│   │   ├── chat.py
│   │   ├── workflow.py
│   │   └── ...
│   │
│   ├── services/
│   │   ├── agent_service.py
│   │   ├── workflow_service.py
│   │   ├── logging_service.py
│   │   └── email_service.py
│   │
│   └── main.py
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── base.css
│   │   └── ...
│   └── js/
│       ├── app.js
│       └── ...
│
├── tests/
│   ├── test_agent_service.py
│   ├── test_logging_service.py
│   ├── test_workflows.py
│   ├── test_approvals.py
│   ├── test_email_tool.py
│   └── ...
│
├── logs/
│   └── application.log
│
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
└── README.md
```

> File names may evolve as additional milestones are implemented.

---

# 🛠️ Technology Stack

| Technology              | Purpose                      |
| ----------------------- | ---------------------------- |
| **Python**              | Backend programming language |
| **FastAPI**             | REST API framework           |
| **LangGraph**           | Agent workflow orchestration |
| **Groq**                | LLM inference                |
| **SQLAlchemy**          | ORM and database access      |
| **SQLite**              | Persistent local database    |
| **Pydantic**            | Data validation and schemas  |
| **Uvicorn**             | ASGI application server      |
| **HTML/CSS/JavaScript** | Frontend dashboard           |
| **Pytest**              | Automated testing            |

---

# 📌 Requirements

Recommended environment:

* Python 3.13+
* pip
* Git
* A Groq API key

---

# ⚙️ Installation

## 1. Clone the repository

```bash
git clone https://github.com/Farihach6/personal-task-agent.git
cd personal-task-agent
```

If your repository URL is different, replace the URL above with your repository URL.

---

## 2. Create a virtual environment

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Windows CMD

```cmd
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Configuration

Create a `.env` file from the provided template:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### Linux / macOS

```bash
cp .env.example .env
```

Then configure the required values.

Example:

```env
APP_NAME=Personal Task Agent

DATABASE_PATH=./data/app.db

GROQ_API_KEY=your_groq_api_key

MAX_AGENT_STEPS=10

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_password
SMTP_FROM=your_email@example.com
```

Do **not** commit your real `.env` file or API credentials to GitHub.

---

# ▶️ Running the Application

Start the application with:

```bash
python run.py
```

The application will be available at:

```text
http://localhost:8000
```

---

# 🌐 Application URLs

## Frontend

```text
http://localhost:8000/
```

## API Documentation

FastAPI automatically provides:

```text
http://localhost:8000/docs
```

and:

```text
http://localhost:8000/redoc
```

## Health Check

```text
http://localhost:8000/api/v1/health
```

---

# 🔌 Main API Endpoints

The API is organized under `/api/v1`.

## Health

```http
GET /api/v1/health
```

Used to verify that the application and database are available.

---

## Chat

```http
POST /api/v1/chat
```

Sends a natural-language request to the Personal Task Agent.

Example:

```json
{
  "message": "Research machine learning and save the important points as a note."
}
```

The agent processes the request through its workflow and returns a response.

---

## Notes

The Notes API provides operations for creating and retrieving persisted notes.

Typical operations include:

```text
POST   /api/v1/notes
GET    /api/v1/notes
GET    /api/v1/notes/{note_id}
PUT    /api/v1/notes/{note_id}
DELETE /api/v1/notes/{note_id}
```

---

## Workflow History

Workflow history is available through:

```text
GET /api/v1/workflows
```

Individual workflow information and its steps can also be retrieved.

The workflow service supports operations such as:

* Create workflow
* Save workflow step
* Complete workflow
* Fail workflow
* Retrieve workflows
* Retrieve a workflow
* Retrieve workflow steps

---

## Execution Logs

Execution logs are available through:

```text
GET /api/v1/logs
```

The endpoint supports retrieving execution information associated with workflows and applying supported filters and limits.

---

## Approvals

The approval API supports human-in-the-loop execution for actions that require authorization.

Approval-related operations allow the application to:

* Inspect pending approval state
* Approve an action
* Reject an action
* Resume a paused workflow

---

# 🧠 Agent Workflow

The agent follows a structured graph rather than executing arbitrary actions directly.

## 1. Reason

The Reason node analyzes the user's request and determines what needs to be accomplished.

```text
User Request
     ↓
Reason
     ↓
Intent / Context
```

---

## 2. Plan

The Plan node determines the steps required to complete the task and identifies the appropriate tools.

```text
Reason
  ↓
Plan
  ↓
Structured Execution Plan
```

---

## 3. Act

The Act node executes the planned action through the `ToolExecutor`.

```text
Plan
  ↓
Act
  ↓
ToolExecutor
  ↓
Selected Tool
```

If a tool requires human approval, the workflow pauses instead of immediately performing the action.

---

## 4. Observe

The Observe node evaluates the result of the previous action.

```text
Tool
  ↓
Result
  ↓
Observe
  ↓
Next Action / Completion
```

This allows the agent to continue multi-step tasks based on actual tool results.

---

# 🔧 Tool Execution

The `ToolExecutor` provides a centralized interface between the LangGraph agent and available tools.

Conceptually:

```text
Agent
  │
  ▼
ToolExecutor
  │
  ├── SearchTool
  │
  ├── NotesTool
  │
  └── EmailTool
```

This design keeps tool selection and execution separate from the individual agent nodes.

---

# 📧 Email and Human Approval

Email functionality is intentionally protected by an approval mechanism.

For an email action requiring approval:

```text
User Request
     ↓
Reason
     ↓
Plan
     ↓
Act
     ↓
Email Tool
     ↓
Approval Required
     ↓
Workflow Paused
     ↓
Human Approval
     ↓
┌───────────────┐
│               │
▼               ▼
Approved      Rejected
│               │
▼               ▼
Send Email    Stop/Handle
```

This prevents potentially consequential actions from being performed without explicit authorization.

---

# 📝 Notes

The Notes Tool allows the agent to persist useful information.

Notes are stored using SQLAlchemy and SQLite.

The notes functionality can be used both through the API and as part of an agent workflow.

For example:

```text
User:
"Research Python decorators and save the key points."

        ↓

Reason
        ↓

Plan
        ↓

Search Tool
        ↓

Observe Search Result
        ↓

Notes Tool
        ↓

Save Note
        ↓

Final Response
```

---

# 📊 Workflow Persistence

Each agent execution can be represented as a workflow.

A workflow may contain steps such as:

```text
REASON
PLAN
ACT
OBSERVE
TOOL
APPROVAL
```

Workflow state is persisted so users can inspect previous executions through the dashboard.

The persistence layer is implemented using:

```text
SQLAlchemy
     +
SQLite
     +
Repository Layer
     +
WorkflowService
```

---

# 📝 Execution Logging Architecture

Execution logging is implemented through a dedicated `LoggingService`.

Instead of allowing every node to implement its own logging behavior, the service centralizes execution event recording.

```text
Reason Node ──────┐
Plan Node ────────┤
Act Node ─────────┼──► LoggingService ──► Python Logger
Observe Node ─────┘              │
                                 ▼
                         execution_logs
                              table
```

The logging service uses an injectable database session factory, making it easier to test and keeping database access isolated.

---

# 🧪 Testing

The project uses **pytest** for automated testing.

Run the complete test suite:

```bash
pytest
```

For more detailed output:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/test_logging_service.py -v
```

---

# 🧪 Test Coverage Areas

The test suite covers multiple layers of the application, including:

### Agent

* Reason node behavior
* Plan node behavior
* Act node behavior
* Observe node behavior
* Graph execution
* Agent service behavior

### Tools

* Search tool
* Notes tool
* Email tool
* Tool executor dispatching

### Workflow

* Workflow creation
* Step persistence
* Workflow completion
* Workflow failure
* Workflow history retrieval
* Workflow step retrieval

### Approval

* Approval-required actions
* Paused workflows
* Approval decisions
* Workflow resume behavior
* Email approval flow

### Logging

* Logging service
* Execution log persistence
* Workflow-associated logs
* Log retrieval

### API

* Chat endpoints
* Notes endpoints
* Workflow endpoints
* Logging endpoints
* Approval endpoints

---

# 🧩 Dependency Injection

The backend uses FastAPI dependency injection and injectable services.

This is particularly important for testing.

For example, services can be replaced with test-specific implementations or database sessions.

The logging system also supports an injectable `session_factory`, allowing tests to use isolated databases instead of the production database.

---

# 🗃️ Database Models

The application currently persists several major entities.

## Workflow

Stores information about an agent execution.

## Workflow Step

Stores individual steps performed during a workflow.

Step types include execution stages such as:

```text
REASON
PLAN
ACT
OBSERVE
APPROVAL
```

## Note

Stores user/agent-generated notes.

## Execution Log

Stores execution events generated while workflows are running.

---

# 🛡️ Guardrails

The architecture is designed to keep agent behavior controlled and observable.

Current safeguards include:

* Maximum agent step configuration
* Tool-based execution instead of unrestricted actions
* Human approval for selected actions
* Workflow persistence
* Execution logging
* Structured agent state
* Centralized tool execution
* Error handling and workflow failure tracking

---

# 📈 Milestone Progress

The project is being developed incrementally.

| Milestone | Feature                                    | Status     |
| --------- | ------------------------------------------ | ---------- |
| 1         | Project Skeleton & Configuration           | ✅ Complete |
| 2         | Database Layer                             | ✅ Complete |
| 3         | Notes Feature                              | ✅ Complete |
| 4         | LLM Client & Basic Agent State             | ✅ Complete |
| 5         | Reason → Plan Nodes                        | ✅ Complete |
| 6         | Search Tool + Act/Observe Nodes            | ✅ Complete |
| 7         | Notes Tool Integration                     | ✅ Complete |
| 8         | Email Tool + Human Approval Flow           | ✅ Complete |
| 9         | Workflow History Persistence & Dashboard   | ✅ Complete |
| 10        | Execution Logs Dashboard                   | ✅ Complete |
| 11        | Chat Frontend Polish & Guardrail Hardening | 🔄 Planned |
| 12        | End-to-End Testing & README Finalization   | 🔄 Planned |

---

# 🗺️ Roadmap

## Milestone 11 — Chat Frontend Polish & Guardrail Hardening

Planned improvements include:

* Chat UI refinement
* Better loading states
* Improved error handling
* Approval UX improvements
* Additional guardrails
* Better frontend/backend integration
* Improved user feedback during long-running tasks

---

## Milestone 12 — Final Testing & Documentation

Planned final work includes:

* End-to-end testing
* Regression testing
* Final documentation
* Deployment preparation
* README refinement
* Final project cleanup

---

# 🔍 Example Workflow

A request such as:

```text
Research the benefits of edge computing,
save the important points as a note,
and prepare an email summary.
```

can be processed as:

```text
                    User Request
                         │
                         ▼
                      Reason
                         │
                         ▼
                       Plan
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
        Search Tool             Notes Tool
             │                       │
             ▼                       ▼
          Observe                Save Note
             │                       │
             └───────────┬───────────┘
                         ▼
                    Email Tool
                         │
                         ▼
                 Approval Required
                         │
                         ▼
                   Human Approval
                         │
                         ▼
                    Send Email
                         │
                         ▼
                  Final Response
```

During execution, important events are recorded in the execution log.

---

# 📋 Example Execution Log

A simplified execution could look like:

```text
Workflow Started
│
├── Reason: Request analyzed
│
├── Plan: Search + Notes + Email
│
├── Act: Search tool executed
│
├── Observe: Search results received
│
├── Act: Notes tool executed
│
├── Observe: Note saved
│
├── Act: Email action requested
│
├── Approval: Waiting for human approval
│
├── Approval: Approved
│
├── Act: Email sent
│
└── Workflow Completed
```

This information can be inspected through the Execution Logs Dashboard.

---

# 🔒 Security Notes

Never commit sensitive credentials.

The following should remain private:

```text
.env
GROQ_API_KEY
SMTP_PASSWORD
SMTP credentials
Database credentials
Other API keys
```

The `.gitignore` file should exclude environment files and other sensitive runtime data.

---

# 🐛 Troubleshooting

## Application does not start

Make sure the virtual environment is activated:

```bash
venv\Scripts\activate
```

Then install dependencies:

```bash
pip install -r requirements.txt
```

---

## Groq API errors

Check that `.env` contains a valid:

```env
GROQ_API_KEY=your_key
```

Restart the application after changing environment variables.

---

## Database errors

Check the configured:

```env
DATABASE_PATH=./data/app.db
```

Make sure the application has permission to create/read the database file.

---

## Port already in use

If port `8000` is already occupied, stop the existing process or run Uvicorn on another port.

For example:

```bash
uvicorn app.main:app --reload --port 8001
```

---

# 🧑‍💻 Development

Recommended development workflow:

```bash
# Activate environment
venv\Scripts\activate

# Install/update dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Start development server
python run.py
```

Before committing changes:

```bash
pytest
git status
git add .
git commit -m "Describe your changes"
```

---

# 📌 Design Principles

The project follows several core principles:

### Separation of Concerns

Agent nodes, tools, services, repositories, API routes, and frontend components have separate responsibilities.

### Reusability

Existing services and repositories are reused instead of duplicating business logic.

### Testability

Database access and services use dependency injection where appropriate to make isolated testing possible.

### Observability

Workflow persistence and execution logging make agent behavior inspectable.

### Controlled Autonomy

The agent can perform multi-step tasks autonomously while selected actions can require human approval.

### Incremental Development

The project is implemented milestone-by-milestone with automated tests and regression protection.

---

# 📚 Learning Objectives

This project demonstrates practical implementation of:

* AI agents
* LangGraph workflows
* LLM integration
* Tool calling
* Multi-step task execution
* Human-in-the-loop systems
* FastAPI
* REST API design
* SQLAlchemy
* SQLite persistence
* Repository pattern
* Dependency injection
* Workflow state management
* Execution logging
* Automated testing
* Frontend/backend integration
* AI agent guardrails

---

# 🎯 Project Goal

The long-term goal of the Personal Task Agent is to provide a reliable AI assistant capable of completing useful multi-step tasks while remaining:

```text
Autonomous
    +
Observable
    +
Testable
    +
Persistent
    +
Controlled
```

The system is intentionally designed so that increasing agent capability does not require sacrificing transparency or user control.

---

# 👩‍💻 Author

**Fariha Ch.**

BS Software Engineering
University of Sargodha

GitHub: `Farihach6`

---

# 📄 License

This project is currently intended for educational, research, and portfolio purposes.

Add an appropriate open-source license here if the project is later released under a specific license.

---

## ⭐ Project Status

**Current Progress: 10 / 12 Milestones Complete**

```text
██████████████████▋░░░ 83%
```

The core Personal Task Agent is functional, including:

* AI reasoning
* Planning
* Tool execution
* Search
* Notes
* Email
* Human approval
* Workflow persistence
* Workflow history dashboard
* Execution logging
* Execution logs dashboard
* Automated tests

The remaining work focuses primarily on frontend polish, additional guardrails, final end-to-end testing, and final project documentation.
