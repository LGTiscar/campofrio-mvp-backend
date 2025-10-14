from src.domain.services.ChatService import ChatService
from src.domain.models.ChatResponse import ChatResponse
from src.infrastructure.azure.AzureFoundryAgentProvider import AzureFoundryAgentProvider
from src.infrastructure.SingletonMeta import SingletonMeta
from azure.ai.agents.models import MessageRole, AgentStreamEvent, MessageDeltaChunk
import logging
import sys
import time

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

class AzureFoundryAgentService(ChatService, metaclass=SingletonMeta):
    def __init__(self):
        self.provider: AzureFoundryAgentProvider = AzureFoundryAgentProvider()
        self.project = self.provider.get_project()
        self.agent = self.provider.get_agent()
        self._logger = logging.getLogger(__name__)

            
    def chat_stream(self, thread_id: str, user_message: str):
        """
        Stream de eventos durante un run del agente. Generador que produce diccionarios con dos campos:
        - type: 'delta' | 'done' | 'error'
        - text: fragmento o texto completo

        El cliente puede consumir estos eventos y mostrarlos incrementalmente.
        """

        # Añade la fecha al system prompt
        fecha = time.strftime("%Y-%m-%d")
        fecha_prompt = f"La fecha actual es {fecha}. Usa esta información en tus respuestas si es relevante."
        
        # Crear el mensaje del usuario
        self.project.agents.messages.create(thread_id, role=MessageRole.USER, content=user_message + "\n" + fecha_prompt)

        # Abrir el stream del run proporcionado por el SDK
        try:
            with self.project.agents.runs.stream(thread_id=thread_id, agent_id=self.agent.id) as stream:
                start = time.time()
                full_text = ""
                for event_type, event_data, _ in stream:
                    # Deltas parciales de texto
                    if isinstance(event_data, MessageDeltaChunk):
                        delta = (event_data.text or "")
                        logger.info(f"Delta generated: {delta}")
                        full_text += delta
                        yield {"type": "delta", "text": delta}

                    # Run completo / fin de stream
                    elif event_type == AgentStreamEvent.DONE:
                        logger.info(f"Run completed in {time.time() - start:.2f} seconds")
                        yield {"type": "done", "text": f"Run completed in {time.time() - start:.2f} seconds: " + full_text}
                        break

                    # Errores
                    elif event_type == AgentStreamEvent.ERROR:
                        yield {"type": "error", "text": str(event_data)}
                        break
                    elif event_type == AgentStreamEvent.THREAD_RUN_FAILED:
                        logger.info(f"Thread run failed: {event_data.last_error}")
                        yield {"type": "error", "text": f"Thread run failed: {event_data.last_error}"}
                        break
                    else:
                        # Ignorar otros eventos por ahora
                        continue
        except Exception as e:
            self._logger.exception("Error while streaming run")
            yield {"type": "error", "text": str(e)}