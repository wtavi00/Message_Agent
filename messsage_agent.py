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

