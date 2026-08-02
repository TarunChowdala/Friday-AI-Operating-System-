"""FastAPI dependency injection helpers."""
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.managers.agent_manager import AgentManager
from app.managers.conversation_manager import ConversationManager
from app.managers.memory_manager import MemoryManager
from app.managers.tool_manager import ToolManager
from app.managers.voice_manager import VoiceManager

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_conversation_manager() -> ConversationManager:
    return ConversationManager()


def get_voice_manager() -> VoiceManager:
    return VoiceManager()


def get_memory_manager() -> MemoryManager:
    return MemoryManager()


def get_tool_manager() -> ToolManager:
    return ToolManager()


def get_agent_manager() -> AgentManager:
    return AgentManager()


ConversationManagerDep = Annotated[ConversationManager, Depends(get_conversation_manager)]
VoiceManagerDep = Annotated[VoiceManager, Depends(get_voice_manager)]
MemoryManagerDep = Annotated[MemoryManager, Depends(get_memory_manager)]
ToolManagerDep = Annotated[ToolManager, Depends(get_tool_manager)]
AgentManagerDep = Annotated[AgentManager, Depends(get_agent_manager)]
