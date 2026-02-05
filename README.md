⸻

⚡ Agentic Workflow Builder

A full-stack Agentic Workflow Builder that lets users design, execute, and monitor multi-step AI workflows using LLMs via the Unbound API.

Each workflow chains AI “agents” together, validates outputs using configurable rules, retries on failure, and automatically passes context between steps.

Built for Unbound Hackathon (Feb 2026).

⸻

🚀 Key Highlights
	•	Workflow Builder UI (HTML + CSS + JS)
	•	Create, edit, delete workflows
	•	Add & reorder steps
	•	Configure model, prompt, criteria, retries, context mode
	•	Agentic Execution Engine
	•	Sequential LLM execution with retries
	•	Context injection between steps
	•	Background execution with live polling
	•	Completion Criteria Engine
	•	contains, regex, json_valid
	•	Step-level pass/fail logic
	•	Live Run Monitoring
	•	Real-time status via polling
	•	Step attempts, outputs, errors
	•	Full execution history
	•	Persistent Storage
	•	SQLite + SQLAlchemy
	•	Workflows, Steps, Runs, RunSteps

⸻

🧱 Tech Stack

Backend
	•	FastAPI, SQLAlchemy, SQLite
	•	Unbound LLM API
	•	BackgroundTasks, httpx

Frontend
	•	Vanilla HTML, CSS, JavaScript
	•	Polling-based live updates (no WebSockets)

⸻

🏗️ Architecture

Workflow → Steps → LLM Call → Criteria Check → Retry / Pass
                                    ↓
                              Context Injection


⸻

📌 Example Use Case
	1.	Generate Python code
	2.	Validate output using regex
	3.	Pass code to next step
	4.	Auto-retry on failure
	5.	Track execution history

⸻

🎯 What This Demonstrates
	•	Agentic system design
	•	LLM orchestration
	•	Backend-frontend coordination
	•	Reliability via retries & validation
	•	Real-time execution monitoring

⸻

👤 Author

Pon Nigitha Varatharajan
Unbound Hackathon – Feb 2026

⸻

