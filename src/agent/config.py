"""Configuration for the standalone Agent layer.

The Agent configuration is intentionally separate from ``config/backend.yaml``.
It controls orchestration safeguards only; model credentials remain owned by
the backend LLM client and are never read while this module is imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Union

import yaml


@dataclass(frozen=True)
class AgentLLMConfig:
    """OpenAI-compatible model settings for the Agent layer."""

    provider: str = "openai_compatible"
    model_name: str = "deepseek-flash"
    api_base: str = "https://api.deepseek.com"
    api_key_env: str = "DEEPSEEK_API_KEY"
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model_name.strip():
            raise ValueError("LLM provider and model_name must not be blank")
        if not self.api_base.strip() or not self.api_key_env.strip():
            raise ValueError("LLM api_base and api_key_env must not be blank")
        if self.timeout_seconds <= 0:
            raise ValueError("LLM timeout_seconds must be greater than zero")


@dataclass(frozen=True)
class AgentConfig:
    """Runtime limits that keep one Agent request bounded and observable."""

    max_iterations: int = 6
    max_repeated_actions: int = 2
    max_tool_calls_per_step: int = 4
    tool_timeout_seconds: float = 15.0
    tool_retry_count: int = 1
    repair_attempts: int = 1
    max_memory_tokens: int = 4000
    summary_trigger_messages: int = 12
    summary_keep_messages: int = 6
    max_workers: int = 4
    timezone: str = "Asia/Shanghai"
    llm: AgentLLMConfig = field(default_factory=AgentLLMConfig)

    def __post_init__(self) -> None:
        positive_ints = {
            "max_iterations": self.max_iterations,
            "max_tool_calls_per_step": self.max_tool_calls_per_step,
            "max_memory_tokens": self.max_memory_tokens,
            "summary_trigger_messages": self.summary_trigger_messages,
            "summary_keep_messages": self.summary_keep_messages,
            "max_workers": self.max_workers,
        }
        for name, value in positive_ints.items():
            if value <= 0:
                raise ValueError(name + " must be greater than zero")
        non_negative_ints = {
            "max_repeated_actions": self.max_repeated_actions,
            "tool_retry_count": self.tool_retry_count,
            "repair_attempts": self.repair_attempts,
        }
        for name, value in non_negative_ints.items():
            if value < 0:
                raise ValueError(name + " must not be negative")
        if self.tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be greater than zero")
        if self.summary_keep_messages > self.summary_trigger_messages:
            raise ValueError("summary_keep_messages must not exceed summary_trigger_messages")
        if not self.timezone.strip():
            raise ValueError("timezone must not be blank")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def load_agent_config(path: Optional[Union[str, Path]] = None) -> AgentConfig:
    """Load Agent settings from YAML, falling back to safe defaults.

    The loader accepts either a top-level ``agent`` mapping plus an optional
    ``memory`` mapping, or a flat mapping.  Missing files are treated as the
    default configuration so importing the Agent does not depend on the
    current working directory.
    """

    config_path = Path(path) if path is not None else Path("config/agent.yaml")
    if not config_path.exists():
        return AgentConfig()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    root = _as_mapping(raw)
    values = dict(_as_mapping(root.get("agent", root)))
    memory = _as_mapping(root.get("memory"))
    aliases = {
        "max_tokens": "max_memory_tokens",
        "summary_trigger": "summary_trigger_messages",
        "summary_keep": "summary_keep_messages",
    }
    for source, target in aliases.items():
        if source in memory and target not in values:
            values[target] = memory[source]
    for key in (
        "max_memory_tokens",
        "summary_trigger_messages",
        "summary_keep_messages",
    ):
        if key in memory:
            values[key] = memory[key]
    llm_values = _as_mapping(root.get("llm"))
    if llm_values:
        llm_allowed = set(AgentLLMConfig.__dataclass_fields__.keys())
        values["llm"] = AgentLLMConfig(
            **{key: value for key, value in llm_values.items() if key in llm_allowed}
        )
    allowed = set(AgentConfig.__dataclass_fields__.keys())
    return AgentConfig(**{key: value for key, value in values.items() if key in allowed})


__all__ = ["AgentConfig", "AgentLLMConfig", "load_agent_config"]
