from src.domain.services.ChatService import ChatService
from src.domain.models.ChatResponse import ChatResponse
from src.infrastructure.azure.AzureFoundryLlmProvider import AzureFoundryLlmProvider
from src.infrastructure.SingletonMeta import SingletonMeta
from azure.ai.agents.models import MessageRole, AgentStreamEvent, MessageDeltaChunk
import logging
import sys

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
        self.provider: AzureFoundryLlmProvider = AzureFoundryLlmProvider()
        self.project = self.provider.get_project()
        self.agent = self.provider.get_agent()
        self._logger = logging.getLogger(__name__)

    def create_thread(self) -> str:
        """
        Crea un nuevo hilo de conversación.
        :return: Identificador del hilo creado.
        """
        thread = self.project.agents.threads.create()
        print(f"Created thread, ID: {thread.id}")
        return thread.id

    def chat(self, thread_id: str, user_message: str) -> ChatResponse | None:
        """
        Envía un mensaje al agente LLM usando el proveedor configurado y espera al resultado final.
        :param thread_id: Identificador del thread donde crear el mensaje.
        :param user_message: Mensaje del usuario para el thread.
        :return ChatResponse: Respuesta del agente LLM.
        """
        message = self.project.agents.messages.create(
            thread_id,
            role=MessageRole.USER,
            content=user_message)

        run = self.project.agents.runs.create_and_process(
            thread_id=thread_id,
            agent_id=self.agent.id,
        )

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
            return None
        else:
            message = self.project.agents.messages.get_last_message_text_by_role(thread_id, MessageRole.AGENT)
            if message is None:
                print("No message found from the agent.")
                return None
            else:
                print(f"Run completed successfully, response: {message.text.value}")
                return ChatResponse(agent_reply=message.text.value)

    def chat_stream(self, thread_id: str, user_message: str):
        """
        Stream de eventos durante un run del agente. Generador que produce diccionarios con dos campos:
        - type: 'delta' | 'done' | 'error'
        - text: fragmento o texto completo

        El cliente puede consumir estos eventos y mostrarlos incrementalmente.
        """
        # Crear el mensaje del usuario
        self.project.agents.messages.create(thread_id, role=MessageRole.USER, content=user_message)

        # Abrir el stream del run proporcionado por el SDK
        try:
            with self.project.agents.runs.stream(thread_id=thread_id, agent_id=self.agent.id, parallel_tool_calls=True) as stream:
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
                        yield {"type": "done", "text": full_text}
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