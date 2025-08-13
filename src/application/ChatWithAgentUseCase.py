from src.application.UseCase import UseCase
from src.domain.services.ChatService import ChatService
from src.domain.models.ChatResponse import ChatResponse

class ChatWithAgentUseCase(UseCase):
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service

    def execute(self, thread_id: str, message: str) -> ChatResponse:
        if not message:
            raise ValueError("Message cannot be empty.")
        
        agent_reply = self.chat_service.chat(thread_id, message)

        return agent_reply