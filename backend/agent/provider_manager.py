"""
Provider manager for LLM backends.

Supports:
  - Local: LM Studio, Ollama, llama.cpp (OpenAI-compatible)
  - Cloud: OpenAI, OpenRouter, Google (OpenAI-compatible), Anthropic
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Optional

from dotenv import set_key
from openai import AsyncOpenAI

try:
    from anthropic import AsyncAnthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    AsyncAnthropic = None
    _ANTHROPIC_AVAILABLE = False

from backend.config import (
    ACTIVE_PROVIDER,
    PROVIDERS_CONFIG,
    PROVIDER_SETTINGS,
    PROVIDERS_STATE_FILE,
    PROVIDER_ENV_KEYS,
)

logger = logging.getLogger(__name__)

PROVIDER_LM_STUDIO = "lm_studio"
PROVIDER_OLLAMA = "ollama"
PROVIDER_LLAMACPP = "llamacpp"
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GOOGLE = "google"
PROVIDER_OPENROUTER = "openrouter"


@dataclass
class ProviderConfig:
    name: str
    display_name: str
    api_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    enabled: bool = True
    category: str = "local"  # local | cloud


PROVIDER_DEFAULTS: dict[str, ProviderConfig] = {
    PROVIDER_LM_STUDIO: ProviderConfig(
        name=PROVIDER_LM_STUDIO,
        display_name="LM Studio",
        api_url="http://localhost:1234/v1",
        model="",
        category="local",
    ),
    PROVIDER_OLLAMA: ProviderConfig(
        name=PROVIDER_OLLAMA,
        display_name="Ollama",
        api_url="http://localhost:11434/v1",
        model="",
        category="local",
    ),
    PROVIDER_LLAMACPP: ProviderConfig(
        name=PROVIDER_LLAMACPP,
        display_name="llama.cpp",
        api_url="http://localhost:8080/v1",
        model="",
        category="local",
    ),
    PROVIDER_OPENAI: ProviderConfig(
        name=PROVIDER_OPENAI,
        display_name="OpenAI",
        api_url="https://api.openai.com/v1",
        model="gpt-4o",
        category="cloud",
    ),
    PROVIDER_OPENROUTER: ProviderConfig(
        name=PROVIDER_OPENROUTER,
        display_name="OpenRouter",
        api_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o",
        category="cloud",
    ),
    PROVIDER_ANTHROPIC: ProviderConfig(
        name=PROVIDER_ANTHROPIC,
        display_name="Anthropic",
        api_url="https://api.anthropic.com/v1",
        model="claude-sonnet-4-20250514",
        category="cloud",
    ),
    PROVIDER_GOOGLE: ProviderConfig(
        name=PROVIDER_GOOGLE,
        display_name="Google Gemini",
        api_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.0-flash",
        category="cloud",
    ),
}

_client_cache: dict[str, object] = {}
_active_provider: Optional[str] = None
_overridden_configs: dict[str, ProviderConfig] = {}


def _load_persisted_state():
    global _active_provider, _overridden_configs
    try:
        if PROVIDERS_STATE_FILE.exists():
            data = json.loads(PROVIDERS_STATE_FILE.read_text(encoding="utf-8"))
            _active_provider = data.get("active", _active_provider)
            for name, vals in data.get("configs", {}).items():
                _overridden_configs[name] = ProviderConfig(
                    name=name,
                    display_name=vals.get("display_name", name),
                    api_url=vals.get("api_url", ""),
                    api_key="",  # API keys only from .env, never from persisted file
                    model=vals.get("model", ""),
                    temperature=float(vals.get("temperature", 0.7)),
                    max_tokens=int(vals.get("max_tokens", 4096)),
                    enabled=bool(vals.get("enabled", True)),
                    category=vals.get("category", "cloud"),
                )
    except Exception as e:
        logger.warning("Failed to load provider state: %s", e)


def _save_persisted_state():
    try:
        data = {
            "active": _active_provider or PROVIDER_LM_STUDIO,
            "configs": {
                name: {
                    "display_name": cfg.display_name,
                    "api_url": cfg.api_url,
                    "model": cfg.model,
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "enabled": cfg.enabled,
                    "category": cfg.category,
                }
                for name, cfg in _overridden_configs.items()
            },
        }
        PROVIDERS_STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save provider state: %s", e)


def _load_configs() -> dict[str, ProviderConfig]:
    configs = {}
    for name, default in PROVIDER_DEFAULTS.items():
        cfg = PROVIDERS_CONFIG.get(name, {})
        configs[name] = ProviderConfig(
            name=name,
            display_name=cfg.get("display_name", default.display_name),
            api_url=cfg.get("api_url", default.api_url),
            api_key=cfg.get("api_key", ""),
            model=cfg.get("model", default.model),
            temperature=float(cfg.get("temperature", default.temperature)),
            max_tokens=int(cfg.get("max_tokens", default.max_tokens)),
            enabled=bool(cfg.get("enabled", True)),
            category=default.category,
        )

    overrides = _overridden_configs
    for name, over in overrides.items():
        if name in configs:
            base = configs[name]
            configs[name] = ProviderConfig(
                name=name,
                display_name=over.display_name or base.display_name,
                api_url=over.api_url or base.api_url,
                api_key=over.api_key or base.api_key,
                model=over.model or base.model,
                temperature=over.temperature or base.temperature,
                max_tokens=over.max_tokens or base.max_tokens,
                enabled=over.enabled,
                category=base.category,
            )
        else:
            configs[name] = over

    return configs


def init_providers():
    global _active_provider
    _active_provider = ACTIVE_PROVIDER or PROVIDER_LM_STUDIO
    _load_persisted_state()
    configs = _load_configs()
    if _active_provider not in configs:
        _active_provider = PROVIDER_LM_STUDIO
    logger.info(
        "Provider manager initialized. Active: %s. Available: %s",
        _active_provider,
        list(configs.keys()),
    )


def get_providers() -> dict[str, ProviderConfig]:
    return _load_configs()


def get_active_provider_name() -> str:
    return _active_provider or PROVIDER_LM_STUDIO


def set_active_provider(name: str) -> bool:
    global _active_provider
    configs = _load_configs()
    if name not in configs:
        logger.warning("Provider '%s' not found", name)
        return False
    _active_provider = name
    _client_cache.clear()
    _save_persisted_state()
    logger.info("Active provider changed to '%s'", name)
    return True


def update_provider_config(name: str, cfg: dict) -> bool:
    configs = _load_configs()
    if name not in configs and name not in PROVIDER_DEFAULTS:
        configs[name] = ProviderConfig(
            name=name,
            display_name=cfg.get("display_name", name),
            api_url=cfg.get("api_url", ""),
            api_key=cfg.get("api_key", ""),
            model=cfg.get("model", ""),
            temperature=float(cfg.get("temperature", 0.7)),
            max_tokens=int(cfg.get("max_tokens", 4096)),
            enabled=bool(cfg.get("enabled", True)),
            category=cfg.get("category", "cloud"),
        )
    _overridden_configs[name] = configs[name]
    for k, v in cfg.items():
        if hasattr(_overridden_configs[name], k) and v is not None:
            setattr(_overridden_configs[name], k, v)

    # Persist API key to .env
    api_key = cfg.get("api_key")
    if api_key is not None and api_key:
        env_var = PROVIDER_ENV_KEYS.get(name)
        if env_var:
            env_path = Path(__file__).resolve().parent.parent / ".env"
            try:
                set_key(str(env_path), env_var, api_key)
                os.environ[env_var] = api_key
                logger.info("Salvata API key per '%s' in .env (%s)", name, env_var)
            except Exception as e:
                logger.warning("Impossibile salvare API key in .env: %s", e)

    _client_cache.clear()
    _save_persisted_state()
    return True


def is_openai_compatible(name: str) -> bool:
    return name in (PROVIDER_LM_STUDIO, PROVIDER_OLLAMA, PROVIDER_LLAMACPP,
                    PROVIDER_OPENAI, PROVIDER_OPENROUTER, PROVIDER_GOOGLE)


def _get_openai_client(cfg: ProviderConfig) -> AsyncOpenAI:
    key = f"openai:{cfg.name}"
    if key not in _client_cache:
        kwargs = {"base_url": cfg.api_url}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        else:
            kwargs["api_key"] = "not-needed"
        _client_cache[key] = AsyncOpenAI(**kwargs)
    return _client_cache[key]


def _get_anthropic_client(cfg: ProviderConfig):
    if not _ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic")
    key = f"anthropic:{cfg.name}"
    if key not in _client_cache:
        _client_cache[key] = AsyncAnthropic(api_key=cfg.api_key)
    return _client_cache[key]


async def stream_chat(
    messages: list,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list | None = None,
    provider_name: str | None = None,
) -> AsyncGenerator[dict, None]:
    active = provider_name or _active_provider or PROVIDER_LM_STUDIO
    configs = _load_configs()
    cfg = configs.get(active)
    if not cfg or not cfg.enabled:
        cfg = configs.get(PROVIDER_LM_STUDIO)
        if not cfg:
            raise RuntimeError("No enabled provider available")

    temp = temperature if temperature is not None else cfg.temperature
    mt = max_tokens if max_tokens is not None else cfg.max_tokens

    system_count = sum(1 for m in messages if m.get("role") == "system")
    logger.debug("[%s] stream_chat: model=%s, system_msgs=%d, user_msgs=%d, tools=%s",
                 cfg.name, cfg.model, system_count, len(messages) - system_count, bool(tools))

    if is_openai_compatible(cfg.name):
        async for chunk in _openai_stream(cfg, messages, temp, mt, tools):
            yield chunk
    elif cfg.name == PROVIDER_ANTHROPIC:
        async for chunk in _anthropic_stream(cfg, messages, temp, mt, tools):
            yield chunk
    else:
        raise RuntimeError(f"Unknown provider: {cfg.name}")


async def chat_once(
    messages: list,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list | None = None,
    provider_name: str | None = None,
):
    active = provider_name or _active_provider or PROVIDER_LM_STUDIO
    configs = _load_configs()
    cfg = configs.get(active)
    if not cfg or not cfg.enabled:
        cfg = configs.get(PROVIDER_LM_STUDIO)
        if not cfg:
            raise RuntimeError("No enabled provider available")

    temp = temperature if temperature is not None else cfg.temperature
    mt = max_tokens if max_tokens is not None else cfg.max_tokens

    system_count = sum(1 for m in messages if m.get("role") == "system")
    logger.debug("[%s] chat_once: model=%s, system_msgs=%d, user_msgs=%d, tools=%s",
                 cfg.name, cfg.model, system_count, len(messages) - system_count, bool(tools))

    if is_openai_compatible(cfg.name):
        return await _openai_chat_once(cfg, messages, temp, mt, tools)
    elif cfg.name == PROVIDER_ANTHROPIC:
        return await _anthropic_chat_once(cfg, messages, temp, mt, tools)
    else:
        raise RuntimeError(f"Unknown provider: {cfg.name}")


# --- OpenAI-compatible (LM Studio, Ollama, llama.cpp, OpenAI, OpenRouter) ---

async def _openai_stream(cfg, messages, temperature, max_tokens, tools):
    client = _get_openai_client(cfg)
    kwargs = {
        "model": cfg.model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools

    stream = await client.chat.completions.create(**kwargs)
    tool_calls_buf = {}

    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_buf:
                    tool_calls_buf[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                if tc.id:
                    tool_calls_buf[idx]["id"] += tc.id
                if tc.function:
                    if tc.function.name:
                        tool_calls_buf[idx]["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_calls_buf[idx]["function"]["arguments"] += tc.function.arguments

        content = delta.content
        if content:
            yield {"type": "token", "content": content}

    if tool_calls_buf:
        tool_calls_list = []
        for idx in sorted(tool_calls_buf.keys()):
            tc = tool_calls_buf[idx]
            tool_calls_list.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                }
            })
        if tool_calls_list:
            yield {"type": "tool_calls", "content": tool_calls_list}


async def _openai_chat_once(cfg, messages, temperature, max_tokens, tools):
    client = _get_openai_client(cfg)
    kwargs = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        response = await client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        # model_dump preserves provider-specific extra fields (e.g. Google's thought_signature)
        msg_dict = msg.model_dump()
        result = {"role": "assistant", "content": msg_dict.get("content") or ""}
        if msg_dict.get("tool_calls"):
            result["tool_calls"] = msg_dict["tool_calls"]
        return result
    except Exception as e:
        logger.error("[%s] chat_once error: %s", cfg.name, e, exc_info=True)
        raise


# --- Anthropic ---

ANTHROPIC_ROLE_MAP = {
    "system": "system",
    "user": "user",
    "assistant": "assistant",
    "tool": "user",
}


async def _anthropic_stream(cfg, messages, temperature, max_tokens, tools):
    client = _get_anthropic_client(cfg)
    system_msgs = [m["content"] for m in messages if m["role"] == "system"]
    system_prompt = "\n".join(system_msgs) if system_msgs else None

    converted = []
    for m in messages:
        role = m["role"]
        if role == "system":
            continue
        if role == "tool":
            converted.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": m["content"],
                }]
            })
        elif role == "assistant" and m.get("tool_calls"):
            content = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": json.loads(tc["function"]["arguments"]),
                })
            converted.append({"role": "assistant", "content": content})
        else:
            converted.append({"role": role, "content": m["content"]})

    kwargs = {
        "model": cfg.model,
        "messages": converted,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if tools:
        kwargs["tools"] = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]

    tool_use_buf = {}

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            if event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    yield {"type": "token", "content": event.delta.text}
            elif event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    idx = event.index
                    tool_use_buf[idx] = {
                        "id": event.content_block.id,
                        "name": event.content_block.name,
                        "input": "",
                    }
            elif event.type == "content_block_delta":
                if event.delta.type == "input_json_delta":
                    for idx in tool_use_buf:
                        tool_use_buf[idx]["input"] += event.delta.partial_json

    if tool_use_buf:
        calls = []
        for idx in sorted(tool_use_buf.keys()):
            tb = tool_use_buf[idx]
            calls.append({
                "id": tb["id"],
                "type": "function",
                "function": {
                    "name": tb["name"],
                    "arguments": tb["input"],
                }
            })
        if calls:
            yield {"type": "tool_calls", "content": calls}


async def _anthropic_chat_once(cfg, messages, temperature, max_tokens, tools):
    """Non-streaming chat for Anthropic (used for tool loops)."""
    system_msgs = [m["content"] for m in messages if m["role"] == "system"]
    system_prompt = "\n".join(system_msgs) if system_msgs else None

    converted = []
    for m in messages:
        role = m["role"]
        if role == "system":
            continue
        if role == "tool":
            converted.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": m["content"],
                }]
            })
        elif role == "assistant" and m.get("tool_calls"):
            content = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": json.loads(tc["function"]["arguments"]),
                })
            converted.append({"role": "assistant", "content": content})
        else:
            converted.append({"role": role, "content": m["content"]})

    client = _get_anthropic_client(cfg)

    kwargs = {
        "model": cfg.model,
        "messages": converted,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if tools:
        kwargs["tools"] = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]

    response = await client.messages.create(**kwargs)

    result = {"role": "assistant", "content": ""}
    for block in response.content:
        if block.type == "text":
            result["content"] += block.text
        elif block.type == "tool_use":
            result.setdefault("tool_calls", []).append({
                "id": block.id,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(block.input),
                }
            })
    return result


def get_provider_info() -> dict:
    configs = _load_configs()

    def _serialize(cfg: ProviderConfig) -> dict:
        return {
            "name": cfg.name,
            "display_name": cfg.display_name,
            "api_url": cfg.api_url,
            "api_key": cfg.api_key,
            "model": cfg.model,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "enabled": cfg.enabled,
            "category": cfg.category,
        }

    return {
        "active": _active_provider or PROVIDER_LM_STUDIO,
        "providers": {name: _serialize(cfg) for name, cfg in configs.items()},
    }


def has_api_key(name: str) -> bool:
    """Check if a provider has a valid API key (from env or runtime config)."""
    configs = _load_configs()
    cfg = configs.get(name)
    if not cfg:
        return False
    return bool(cfg.api_key) or cfg.category == "local"
