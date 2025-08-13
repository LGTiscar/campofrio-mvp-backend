from src.domain.providers.LLMProvider import LLMProvider
from src.domain.models.ChatResponse import ChatResponse
from abc import abstractmethod

class ChatService:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    @abstractmethod
    def create_thread(self):
        """Crea un nuevo hilo de conversación.
        :return: Identificador del hilo creado.
        """
        pass
    
    def chat(self, message: str, thread_id: str) -> ChatResponse:
        """
        Envía un mensaje al agente LLM usando el proveedor configurado.
        :param message: Mensaje de entrada.
        :param context: Contexto opcional para la conversación.
        :return: Respuesta del agente LLM.
        """
        return ChatResponse(agent_reply='')