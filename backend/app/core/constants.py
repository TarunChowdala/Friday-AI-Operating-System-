"""Shared constants."""

APP_NAME = "JARVIS AI"
APP_VERSION = "4.2.1"

# AI states mirrored by frontend
AI_STATES = ("idle", "listening", "thinking", "speaking", "executing", "error")

# WebSocket event types
WS_EVENT_STATUS = "status"
WS_EVENT_TRANSCRIPT = "transcript"
WS_EVENT_RESPONSE = "response"
WS_EVENT_TOOL = "tool"
WS_EVENT_ERROR = "error"
WS_EVENT_SYSTEM = "system"

# Memory
SHORT_TERM_MAX_MESSAGES = 20
DEFAULT_TOP_K = 5

# Audio
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
