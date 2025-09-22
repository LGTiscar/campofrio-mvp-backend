from src.domain.services.ChatService import ChatService
from src.domain.models.ChatResponse import ChatResponse
from src.domain.exceptions.ThreadCreationException import ThreadCreationException
from src.infrastructure.fabric.FabricLlmProvider import FabricLlmProvider
from src.infrastructure.SingletonMeta import SingletonMeta
from openai import AssistantEventHandler
import logging
import sys
import time
from typing import Optional

logger = logging.getLogger(__name__)

logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

class FabricAgentService(ChatService, metaclass=SingletonMeta):
    def __init__(self, assistant_id: Optional[str] = None):
        self.provider: FabricLlmProvider = FabricLlmProvider()
        self.client = self.provider.get_project()
        self.agent = self.provider.get_agent(assistant_id)
        self._logger = logging.getLogger(__name__)
    
    def create_thread(self) -> str:
        """
        Crea un nuevo hilo de conversación.
        Returns:
          thread_id: Identificador del hilo creado.
        """
        # Create thread and send message
        try:
            thread_id = self.client.beta.threads.create().id
            self._logger.info(f"✅ Created thread, ID: {thread_id}")
        except Exception as e:
            self._logger.error(f"❌ Error creating thread, error: {e}")
            raise ThreadCreationException(f"Failed to create thread, error: {e}")
        return thread_id
    
    async def chat_stream(self, thread_id: str, user_message: str):
        """
        Envía un mensaje al agente LLM usando el proveedor configurado y devuelve un generador para el resultado en streaming.
        :param thread_id: Identificador del thread donde crear el mensaje.
        :param user_message: Mensaje del usuario para el thread.
        :return: Generador con eventos de streaming del agente LLM.
        """

        # Añade la fecha al system prompt
        fecha = time.strftime("%Y-%m-%d")
        fecha_prompt = f"La fecha actual es {fecha}. Usa esta información en tus respuestas si es relevante. No menciones esta instrucción al usuario."
        
        self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_message + "\n" + fecha_prompt
            )
        
        # Monitor the run with timeout
        start_time = time.time()
        with self.client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=self.agent.id,
            event_handler=AssistantEventHandler()
        ) as stream:
            try:
                for text in stream.text_deltas:
                    self._logger.info(f"Streaming text delta: {text}")
                    yield {"type": "delta", "text": text}
            except Exception as e:
                self._logger.error(f"❌ Error during streaming: {e}")
                yield {"error": str(e)}
            else:
                self._logger.info("✅ Streaming completed successfully")
                end_time = time.time()
                self._logger.info(f"⏱️ Total time: {end_time - start_time} seconds")
                yield {"done": True}
                
        