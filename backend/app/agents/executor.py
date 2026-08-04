from typing import Any, Dict
from langchain_core.prompts import PromptTemplate
from app.core.logger import get_logger
from app.core.llm import get_llm
from app.tools.system_controls import (
    change_volume, 
    open_application, 
    open_url, 
    search_google, 
    play_youtube,
    run_terminal_command,
    media_control,
    clipboard_control,
    capture_screen_and_analyze
)

logger = get_logger(__name__)

class ExecutorAgent:
    name = "executor"

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.0)
        self.tools = [
            change_volume, 
            open_application, 
            open_url, 
            search_google, 
            play_youtube,
            run_terminal_command,
            media_control,
            clipboard_control,
            capture_screen_and_analyze
        ]
        
        # Bind the tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        return {"agent": self.name, "task": task, "result": "Executor ran.", "context_keys": list(context.keys())}

    async def stream(self, task: str, context: Dict[str, Any] | None = None):
        """Streams the LLM response. If it calls a tool, we execute it."""
        logger.info("ExecutorAgent analyzing task: %s", task[:80])
        try:
            # Yield a filler phrase instantly
            yield "Processing command now. "

            # Send the task to LLM with tools bound
            response = await self.llm_with_tools.ainvoke(f"User request: {task}")
            
            # Check if the LLM decided to call a tool
            if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
                import asyncio
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    logger.info(f"LLM invoked tool: {tool_name} with args {tool_args}")
                    
                    if tool_name == "change_volume":
                        asyncio.create_task(asyncio.to_thread(change_volume.invoke, tool_args))
                        yield f"I have set the volume to {tool_args.get('level')} percent."
                    elif tool_name == "open_application":
                        app_name = tool_args.get('app_name', 'application')
                        asyncio.create_task(asyncio.to_thread(open_application.invoke, tool_args))
                        yield f"Opening {app_name} for you."
                    elif tool_name == "open_url":
                        url = tool_args.get('url', '')
                        asyncio.create_task(asyncio.to_thread(open_url.invoke, tool_args))
                        yield f"Opening link in your browser."
                    elif tool_name == "search_google":
                        query = tool_args.get('query', '')
                        asyncio.create_task(asyncio.to_thread(search_google.invoke, tool_args))
                        yield f"Searching Google for {query}."
                    elif tool_name == "play_youtube":
                        query = tool_args.get('query', '')
                        asyncio.create_task(asyncio.to_thread(play_youtube.invoke, tool_args))
                        yield f"Playing {query} on YouTube."
                    elif tool_name == "run_terminal_command":
                        cmd = tool_args.get('command', '')
                        result = await asyncio.to_thread(run_terminal_command.invoke, tool_args)
                        yield f"{result}"
                    elif tool_name == "media_control":
                        act = tool_args.get('action', '')
                        asyncio.create_task(asyncio.to_thread(media_control.invoke, tool_args))
                        yield f"Executing media control."
                    elif tool_name == "clipboard_control":
                        act = tool_args.get('action', '')
                        result = await asyncio.to_thread(clipboard_control.invoke, tool_args)
                        yield f"{result}"
                    elif tool_name == "capture_screen_and_analyze":
                        prompt = tool_args.get('prompt', 'Describe the screen')
                        result = await asyncio.to_thread(capture_screen_and_analyze.invoke, tool_args)
                        yield f"{result}"
                    else:
                        yield f"I tried to run {tool_name}, but it's not fully configured yet."

            else:
                # If no tool was called, just yield the text
                if hasattr(response, 'content') and response.content:
                    yield response.content
                else:
                    yield "I couldn't figure out which system command to run."
                    
        except Exception as e:
            logger.error("ExecutorAgent failed: %s", e)
            yield "I encountered a system error while trying to run that command."

