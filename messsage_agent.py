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


