"""
LLM client — delegates to provider_manager for multi-provider support.

Legacy functions (stream_chat, chat_once) kept for backward compatibility.
All routing logic lives in provider_manager.py.
"""

from backend.agent.provider_manager import stream_chat, chat_once

__all__ = ["stream_chat", "chat_once"]
