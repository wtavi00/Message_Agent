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
