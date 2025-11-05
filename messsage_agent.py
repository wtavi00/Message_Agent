from __future__ import annotations

import json
import os
import re
import signal
import sys
import math
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.request
import urllib.parse


@dataclass
class AgentResponse:
    text: str
    intent: str = "unknown"
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


Preprocessor = Callable[[str], str]
Postprocessor = Callable[[AgentResponse], AgentResponse]
Predicate = Callable[[str, Dict[str, Any]], bool]
Handler = Callable[[str, Dict[str, Any]], AgentResponse]

class MessageAgent:
    """
    A lightweight, extensible agent for handling user messages.

    Features:
    - Rule-based handler registry with predicates
    - Simple persistent memory (JSON file)
    - Pluggable pre/post-processors
    - Built-in intents including reminders, notes, tasks, and web search
    """
    
    def __init__(
        self,
        memory_path: str = ".agent_memory.json",
        preprocessors: Optional[List[Preprocessor]] = None,
        postprocessors: Optional[List[Postprocessor]] = None,
    ) -> None:
        self.memory_path = memory_path
        self._memory: Dict[str, Any] = {}
        self._handlers: List[Tuple[Predicate, Handler]] = []
        self._preprocessors: List[Preprocessor] = preprocessors or []
        self._postprocessors: List[Postprocessor] = postprocessors or []

        self._install_default_handlers()
        self._load_memory()

    # ------------------------ Public API ------------------------
    def register_handler(self, predicate: Predicate, handler: Handler) -> None:
        self._handlers.append((predicate, handler))

    def add_preprocessor(self, preprocessor: Preprocessor) -> None:
        self._preprocessors.append(preprocessor)

    def add_postprocessor(self, postprocessor: Postprocessor) -> None:
        self._postprocessors.append(postprocessor)

    def process(self, message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        if context is None:
            context = {}

        original_message = message
        for preprocessor in self._preprocessors:
            try:
                message = preprocessor(message)
            except Exception as preprocessor_error:
                return AgentResponse(
                    text=f"Preprocessor error: {preprocessor_error}",
                    intent="error",
                    confidence=1.0,
                    metadata={"stage": "preprocessor"},
                )

        for predicate, handler in self._handlers:
            try:
                if predicate(message, context):
                    response = handler(message, context)
                    response.metadata.setdefault("received_at", datetime.utcnow().isoformat() + "Z")
                    response.metadata.setdefault("original_message", original_message)
                    break
            except Exception as handler_error:
                response = AgentResponse(
                    text=f"Handler error: {handler_error}",
                    intent="error",
                    confidence=1.0,
                    metadata={"stage": "handler"},
                )
                break
        else:
            response = self._fallback_handler(message, context)

        for postprocessor in self._postprocessors:
            try:
                response = postprocessor(response)
            except Exception as postprocessor_error:
                return AgentResponse(
                    text=f"Postprocessor error: {postprocessor_error}",
                    intent="error",
                    confidence=1.0,
                    metadata={"stage": "postprocessor"},
                )

        self._save_memory()
        return response

    def reset_memory(self) -> None:
        self._memory = {}
        self._save_memory()

    def __str__(self) -> str:
        return f"<MessageAgent handlers={len(self._handlers)} memory_keys={list(self._memory.keys())}>"

    # ------------------------ Defaults ------------------------
    def _install_default_handlers(self) -> None:
        # keep existing preprocessors
        self.add_preprocessor(lambda m: m.strip())
        self.add_preprocessor(lambda m: re.sub(r"\s+", " ", m))

        # ---------------- GREETING ----------------
        def is_greeting(message: str, _: Dict[str, Any]) -> bool:
            return bool(re.search(r"\b(hi|hello|hey)\b", message, re.IGNORECASE))

        def handle_greeting(message: str, context: Dict[str, Any]) -> AgentResponse:
            user_name = context.get("user_name") or self._memory.get("user_name")
            if not user_name:
                # best-effort extraction
                name_match = re.search(r"i\s*'?m\s+(?P<name>[A-Za-z][A-Za-z\-']{1,29})", message, re.IGNORECASE)
                if name_match:
                    user_name = name_match.group("name")
                    self._memory["user_name"] = user_name
            greeting_name = f", {user_name}" if user_name else ""
            return AgentResponse(
                text=f"Hello{greeting_name}! How can I help you today?",
                intent="greet",
                confidence=0.95,
            )

        self.register_handler(is_greeting, handle_greeting)

        # ---------------- HELP ----------------
        def is_help(message: str, _: Dict[str, Any]) -> bool:
            return any(keyword in message.lower() for keyword in ["help", "what can you do", "commands", "?help"])

        def handle_help(_: str, __: Dict[str, Any]) -> AgentResponse:
            help_text = (
                "I can:\n"
                "- Respond to greetings, goodbyes, and echo text.\n"
                "- Calculate math: 'calc 2+2*5'.\n"
                "- Tell age: 'age 2000-05-17'.\n"
                "- Check leap year: 'leap 2024'.\n\n"
                "NEW FEATURES:\n"
                "- Reminders: 'remind me to call mom in 2 hours' or 'remind buy milk tomorrow'.\n"
                "- Notes: 'note remember password is 1234' or 'notes' to list all.\n"
                "- Tasks: 'task buy groceries' or 'tasks' to list, 'done 1' to complete.\n"
                "- Search: 'search python tutorials' or 'search weather today'.\n\n"
                "Use '/reset' to clear memory."
            )
            return AgentResponse(text=help_text, intent="help", confidence=0.9)

        self.register_handler(is_help, handle_help)

        # ---------------- FAREWELL ----------------
        def is_farewell(message: str, _: Dict[str, Any]) -> bool:
            return bool(re.search(r"\b(bye|goodbye|see ya|ttyl)\b", message, re.IGNORECASE))

        def handle_farewell(_: str, __: Dict[str, Any]) -> AgentResponse:
            return AgentResponse(text="Goodbye! 👋", intent="farewell", confidence=0.9)

        self.register_handler(is_farewell, handle_farewell)

        # ---------------- ECHO ----------------
        def is_echo(message: str, _: Dict[str, Any]) -> bool:
            return message.lower().startswith("/echo ") or message.lower() == "/echo"
            
        def handle_echo(message: str, _: Dict[str, Any]) -> AgentResponse:
            parts = message.split(" ", 1)
            text_to_echo = parts[1] if len(parts) > 1 else ""
            return AgentResponse(text=text_to_echo, intent="echo", confidence=0.99)

        self.register_handler(is_echo, handle_echo)

        # ---------------- CALCULATION ----------------
        def is_calc(message: str, _: Dict[str, Any]) -> bool:
            return message.lower().startswith("calc ")

        def handle_calc(message: str, _: Dict[str, Any]) -> AgentResponse:
            expr = message[5:].strip()
            try:
                # Safe eval: only math functions and numbers
                allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
                result = eval(expr, {"__builtins__": {}}, allowed_names)
                return AgentResponse(text=f"Result: {result}", intent="calc", confidence=0.95)
            except Exception as e:
                return AgentResponse(text=f"Error in calculation: {e}", intent="error", confidence=1.0)

        self.register_handler(is_calc, handle_calc)

        # ---------------- AGE ----------------
        def is_age(message: str, _: Dict[str, Any]) -> bool:
            return message.lower().startswith("age ")

        def handle_age(message: str, _: Dict[str, Any]) -> AgentResponse:
            try:
                dob_str = message.split(" ", 1)[1].strip()
                dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                return AgentResponse(text=f"You are {age} years old.", intent="age", confidence=0.95)
            except Exception:
                return AgentResponse(
                    text="Usage: age YYYY-MM-DD (example: age 2000-05-17)",
                    intent="error",
                    confidence=1.0,
                )

        self.register_handler(is_age, handle_age)

        # ---------------- LEAP YEAR ----------------
        def is_leap(message: str, _: Dict[str, Any]) -> bool:
            return message.lower().startswith("leap ")

        def handle_leap(message: str, _: Dict[str, Any]) -> AgentResponse:
            try:
                year = int(message.split(" ", 1)[1].strip())
                is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                return AgentResponse(
                    text=f"{year} is {'a leap year' if is_leap else 'not a leap year'}.",
                    intent="leap_year",
                    confidence=0.95,
                )
            except Exception:
                return AgentResponse(text="Usage: leap YEAR (example: leap 2024)", intent="error", confidence=1.0)

        self.register_handler(is_leap, handle_leap)

        # ---------------- REMINDERS ----------------
        def is_reminder(message: str, _: Dict[str, Any]) -> bool:
            msg_lower = message.lower()
            return msg_lower.startswith("remind") or msg_lower == "reminders"


        def handle_reminder(message: str, _: Dict[str, Any]) -> AgentResponse:
            msg_lower = message.lower()
            
            # List reminders
            if msg_lower == "reminders":
                reminders = self._memory.get("reminders", [])
                if not reminders:
                    return AgentResponse(text="No reminders set.", intent="reminder_list", confidence=0.95)
                
                now = datetime.now()
                active = []
                for idx, r in enumerate(reminders, 1):
                    due = datetime.fromisoformat(r["due_time"])
                    status = "⏰ DUE" if due <= now else f"⏳ {self._format_time_left(due - now)}"
                    active.append(f"{idx}. {r['text']} - {status}")
                
                return AgentResponse(
                    text="Your reminders:\n" + "\n".join(active),
                    intent="reminder_list",
                    confidence=0.95
                )

            # Set reminder
            try:
                # Parse time delta
                time_match = re.search(r'in (\d+) (minute|minutes|hour|hours|day|days)', msg_lower)
                when_match = re.search(r'(tomorrow|today)', msg_lower)
                
                due_time = None
                
                if time_match:
                    amount = int(time_match.group(1))
                    unit = time_match.group(2)
                    
                    if 'minute' in unit:
                        due_time = datetime.now() + timedelta(minutes=amount)
                    elif 'hour' in unit:
                        due_time = datetime.now() + timedelta(hours=amount)
                    elif 'day' in unit:
                        due_time = datetime.now() + timedelta(days=amount)
                        
                elif when_match:
                    when = when_match.group(1)
                    if when == "tomorrow":
                        due_time = datetime.now() + timedelta(days=1)
                        due_time = due_time.replace(hour=9, minute=0, second=0, microsecond=0)
                    elif when == "today":
                        due_time = datetime.now() + timedelta(hours=1)
                
                if not due_time:
                    return AgentResponse(
                        text="Usage: 'remind me to [task] in [X] hours/days' or 'remind [task] tomorrow'",
                        intent="error",
                        confidence=1.0
                    )

                # Extract reminder text
                reminder_text = re.sub(r'remind(me)?\s+(to\s+)?', '', message, flags=re.IGNORECASE)
                reminder_text = re.sub(r'in \d+ (minute|minutes|hour|hours|day|days)', '', reminder_text, flags=re.IGNORECASE)
                reminder_text = re.sub(r'(tomorrow|today)', '', reminder_text, flags=re.IGNORECASE)
                reminder_text = reminder_text.strip()
                
                if not reminder_text:
                    reminder_text = "Reminder"
                    
                # Store reminder
                reminders = self._memory.setdefault("reminders", [])
                reminders.append({
                    "text": reminder_text,
                    "due_time": due_time.isoformat(),
                    "created": datetime.now().isoformat()
                })
                
                time_str = due_time.strftime("%I:%M %p on %b %d")
                return AgentResponse(
                    text=f"✓ Reminder set: '{reminder_text}' at {time_str}",
                    intent="reminder_set",
                    confidence=0.95
                )
                
            except Exception as e:
                return AgentResponse(
                    text=f"Error setting reminder: {e}",
                    intent="error",
                    confidence=1.0
                )

        self.register_handler(is_reminder, handle_reminder)
        
        # ---------------- NOTES ----------------
        def is_note(message: str, _: Dict[str, Any]) -> bool:
            msg_lower = message.lower()
            return msg_lower.startswith("note ") or msg_lower == "notes"
            
        def handle_note(message: str, _: Dict[str, Any]) -> AgentResponse:
            msg_lower = message.lower()
            
            # List notes
            if msg_lower == "notes":
                notes = self._memory.get("notes", [])
                if not notes:
                    return AgentResponse(text="No notes saved.", intent="note_list", confidence=0.95)
                
                note_list = []
                for idx, note in enumerate(notes, 1):
                    timestamp = datetime.fromisoformat(note["created"]).strftime("%b %d, %I:%M %p")
                    note_list.append(f"{idx}. {note['text']} ({timestamp})")
                
                return AgentResponse(
                    text="Your notes:\n" + "\n".join(note_list),
                    intent="note_list",
                    confidence=0.95
                )
                
            # Add note
            note_text = message[5:].strip()
            if not note_text:
                return AgentResponse(
                    text="Usage: 'note [your note text]' or 'notes' to list all",
                    intent="error",
                    confidence=1.0
                )
            notes = self._memory.setdefault("notes", [])
            notes.append({
                "text": note_text,
                "created": datetime.now().isoformat()
            })
            
            return AgentResponse(
                text=f"✓ Note saved: '{note_text}'",
                intent="note_add",
                confidence=0.95
            )

        self.register_handler(is_note, handle_note)

        # ---------------- TASKS ----------------
        def is_task(message: str, _: Dict[str, Any]) -> bool:
            msg_lower = message.lower()
            return (msg_lower.startswith("task ") or msg_lower == "tasks" or 
                    msg_lower.startswith("done ") or msg_lower.startswith("delete task "))

        def handle_task(message: str, _: Dict[str, Any]) -> AgentResponse:
            msg_lower = message.lower()
            
            # List tasks
            if msg_lower == "tasks":
                tasks = self._memory.get("tasks", [])
                if not tasks:
                    return AgentResponse(text="No tasks found.", intent="task_list", confidence=0.95)
                
                pending = []
                completed = []

                for idx, task in enumerate(tasks, 1):
                    status = "✓" if task.get("completed") else "○"
                    task_str = f"{idx}. {status} {task['text']}"
                    if task.get("completed"):
                        completed.append(task_str)
                    else:
                        pending.append(task_str)

                result = []
                if pending:
                    result.append("Pending:\n" + "\n".join(pending))
                if completed:
                    result.append("Completed:\n" + "\n".join(completed))
                
                return AgentResponse(
                    text="\n\n".join(result) if result else "No tasks found.",
                    intent="task_list",
                    confidence=0.95
                )
            
            # Mark task as done
            if msg_lower.startswith("done "):
                try:
                    task_num = int(message.split()[1])
                    tasks = self._memory.get("tasks", [])
                    
                    if 1 <= task_num <= len(tasks):
                        tasks[task_num - 1]["completed"] = True
                        tasks[task_num - 1]["completed_at"] = datetime.now().isoformat()
                        return AgentResponse(
                            text=f"✓ Task {task_num} marked as done!",
                            intent="task_complete",
                            confidence=0.95
                        )
                    else:
                        return AgentResponse(
                            text=f"Task {task_num} not found.",
                            intent="error",
                            confidence=1.0
                        )
                except (ValueError, IndexError):
                    return AgentResponse(
                        text="Usage: 'done [task number]' (example: done 1)",
                        intent="error",
                        confidence=1.0
                    )
