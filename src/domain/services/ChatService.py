from src.domain.providers.LLMProvider import LLMProvider
from src.domain.models.ChatResponse import ChatResponse

class ChatService:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    
    def chat(self, message: str, thread_id: str) -> ChatResponse:
        """
        Envía un mensaje al agente LLM usando el proveedor configurado.
        :param message: Mensaje de entrada.
        :param context: Contexto opcional para la conversación.
        :return: Respuesta del agente LLM.
        """
        return ChatResponse(agent_reply='')