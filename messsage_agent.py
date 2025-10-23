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

