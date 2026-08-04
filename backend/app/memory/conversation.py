from typing import List, Dict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from app.core.logger import get_logger
from app.core.llm import get_llm

logger = get_logger(__name__)

class ConversationMemoryManager:
    def __init__(self, max_messages: int = 10):
        self.max_messages = max_messages
        self._memory_store: Dict[str, List[BaseMessage]] = {}
        self._summaries: Dict[str, str] = {}
        
        # We use a fast model for summarization
        self.summarizer_llm = get_llm(purpose="summarization", temperature=0.3)
        
    def _get_base_system_prompt(self, summary: str = "") -> SystemMessage:
        base = (
            "You are FRIDAY, an exceptionally intelligent, polite, and witty personal AI assistant.\n"
            "Speak naturally, eloquently, and concisely.\n"
            "You may occasionally address the user as 'Boss' or by title, but DO NOT overuse it in every response—use it sparingly and naturally."
        )
        if summary:
            base += f"\n\nHere is a summary of the earlier conversation:\n{summary}"
        return SystemMessage(content=base)


    def get_messages(self, client_id: str) -> List[BaseMessage]:
        """Returns the full context array (SystemMessage + Chat History) for a client."""
        if client_id not in self._memory_store:
            self._memory_store[client_id] = []
        if client_id not in self._summaries:
            self._summaries[client_id] = ""
            
        summary = self._summaries.get(client_id, "")
        system_message = self._get_base_system_prompt(summary)
        return [system_message] + self._memory_store[client_id]


    def add_human_message(self, client_id: str, content: str):
        if client_id not in self._memory_store:
            self._memory_store[client_id] = []
        self._memory_store[client_id].append(HumanMessage(content=content))

    def add_ai_message(self, client_id: str, content: str):
        if client_id not in self._memory_store:
            self._memory_store[client_id] = []
        self._memory_store[client_id].append(AIMessage(content=content))
        
        # After AI responds, check if we need to summarize
        self._check_and_summarize(client_id)

    def _check_and_summarize(self, client_id: str):
        messages = self._memory_store[client_id]
        
        if len(messages) > self.max_messages:
            logger.info(f"Conversation length ({len(messages)}) exceeded limit ({self.max_messages}). Summarizing...")
            
            # Keep the last 4 messages for immediate context, summarize the rest
            messages_to_keep = messages[-4:]
            messages_to_summarize = messages[:-4]
            
            current_summary = self._summaries.get(client_id, "")
            
            # Build the summarization prompt
            summary_prompt = (
                "You are an AI maintaining a conversation summary.\n"
                f"Current summary:\n{current_summary}\n\n"
                "New conversation turns to incorporate:\n"
            )
            for m in messages_to_summarize:
                role = "User" if isinstance(m, HumanMessage) else "FRIDAY"
                summary_prompt += f"{role}: {m.content}\n"
                
            summary_prompt += "\nUpdate the summary to include the new information. Keep it concise."
            
            try:
                # Ask the summarizer LLM to compress it
                response = self.summarizer_llm.invoke(summary_prompt)
                new_summary = response.content if hasattr(response, 'content') else str(response)
                
                self._summaries[client_id] = new_summary
                self._memory_store[client_id] = messages_to_keep
                logger.info("Successfully updated conversation summary.")
                
            except Exception as e:
                logger.error(f"Failed to summarize conversation: {e}")

# Global instance for the server
conversation_memory = ConversationMemoryManager()
