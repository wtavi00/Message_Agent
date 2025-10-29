# 🧠 Message_Agent — A Lightweight Extensible Chat Agent

**Message_Agent** is a simple yet powerful Python-based conversational agent that can process user messages, remember state between runs, and handle commands like reminders, notes, tasks, and searches — all without external dependencies or complex AI APIs.

It’s designed to be **modular, extensible, and developer-friendly**, making it ideal for embedding lightweight chat capabilities or experimenting with agent design.

Message_Agent is your pocket-sized personal assistant — simple, smart, and scriptable.

---

## 🚀 Features

- **Predefined intelligent handlers**
  - Greetings (`hi`, `hello`, `hey`)
  - Help and command list
  - Farewell (`bye`, `goodbye`)
  - Echo (`/echo message`)
  - Calculations (`calc 2+3*5`)
  - Age calculation (`age 2000-05-17`)
  - Leap year check (`leap 2024`)
  - Reminders (`remind me to call mom in 2 hours`)
  - Notes (`note remember the password`)
  - Tasks (`task buy groceries`, `done 1`, `tasks`)
  - Web search via DuckDuckGo (`search python tutorials`)
- **Persistent memory** using a local JSON file (`.agent_memory.json`)
- **Extensible handler system**
  - Easily register new message types with predicates and handlers
- **Preprocessors and postprocessors**
  - For input/output transformation or logging
- **Command-line interface (CLI)** with REPL mode and one-shot execution

---

## 🧩 Example Usage

### 🖥️ Run interactively

```bash
python message_agent.py
Sample session:

Enhanced Message Agent ready. Type '/help' for options.

> hello
Hello! How can I help you today?

> calc 2+5*10
Result: 52

> remind me to submit report in 2 hours
✓ Reminder set: 'submit report' at 01:23 PM on Oct 19

> notes
No notes saved.

> note remember API key 12345
✓ Note saved: 'remember API key 12345'

> tasks
No tasks found.

> task finish project
✓ Task added: 'finish project'

> tasks
Pending:
1. ○ finish project

> done 1
✓ Task 1 marked as done!

> bye
Goodbye! 👋
```

## ⚙️ Installation
Clone the repository and run with Python 3.8+:

```bash

git clone https://github.com/yourusername/Message_Agent.git
cd MessageAgent
python message_agent.py
```

No external dependencies are required — it runs on the Python standard library only.

## 🧠 Memory and Persistence
All notes, reminders, and tasks are stored in a local JSON file:
```bash
.agent_memory.json
You can clear it anytime via:
```

```bash
/reset
```

## 🧰 CLI Commands
```
Command	Description
/help	Show command help
/echo TEXT	Echo back any text
/reset	Clear saved memory
/whoami NAME	Set your name for greetings
/quit	Exit the agent
```

## 🪄 Supported Natural Commands
```
Intent	Example	Description
Greeting	hello, hi there	Friendly greeting
Calculation	calc 5 * (3 + 2)	Math evaluation
Age	age 2000-05-17	Calculates age
Leap Year	leap 2024	Checks leap year
Reminder	remind me to call mom in 2 hours	Sets reminders
Notes	note buy milk / notes	Add or list notes
Tasks	task clean room / done 1 / tasks	Manage tasks
Search	search python tutorials	Web search (DuckDuckGo)
```

## 🧩 Extending the Agent
MessageAgent uses a predicate-handler architecture.

You can easily register new behaviors:

```bash
def is_weather(message: str, _: dict) -> bool:
    return message.lower().startswith("weather ")

def handle_weather(message: str, _: dict) -> AgentResponse:
    city = message.split(" ", 1)[1]
    return AgentResponse(text=f"Fetching weather for {city}...", intent="weather", confidence=0.9)

agent.register_handler(is_weather, handle_weather)
```

## 🧱 Project Structure
```bash
MessageAgent/
│
├── message_agent.py
├── .agent_memory.json       # Persistent storage (auto-created)
└── README.md
```

## 🧩 Design Highlights
- No dependencies: 100% Python stdlib

- Safe math evaluation: restricted eval() environment

- Graceful error handling: per-stage error recovery (pre/post/handler)

- Customizable: add your own preprocessors and postprocessors
