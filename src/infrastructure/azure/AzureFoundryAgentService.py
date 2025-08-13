from src.domain.services.ChatService import ChatService
from src.domain.models.ChatResponse import ChatResponse
from src.infrastructure.azure.AzureFoundryLlmProvider import AzureFoundryLlmProvider
from azure.ai.agents.models import MessageRole


class AzureFoundryAgentService(ChatService):
    def __init__(self):
        
        self.provider: AzureFoundryLlmProvider = AzureFoundryLlmProvider()
        self.project = self.provider.get_project()
        self.agent = self.provider.get_agent()
    
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
        Envía un mensaje al agente LLM usando el proveedor configurado.
        :param thread_id: Identificador del thread donde crear el mensaje.
        :param user_message: Mensaje del usuario para el thread.
        :return ChatResponse: Respuesta del agente LLM.
        """
        message = self.project.agents.messages.create(
            thread_id,
            role=MessageRole.USER,
            content = user_message)

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
        