from src.domain.providers.LLMProvider import LLMProvider
from src.infrastructure.SingletonMeta import SingletonMeta
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import FabricTool, Agent
from dotenv import load_dotenv
import os
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

class AzureFoundryAgentProvider(LLMProvider, metaclass=SingletonMeta):

    def __init__(self):

        load_dotenv()
        self.project = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=os.environ["PROJECT_ENDPOINT"]
        )
        self.fabric = FabricTool(connection_id=os.environ["FABRIC_CONNECTION_ID"])
        
    
    def create_thread(self) -> str:
        """
        Crea un nuevo hilo de conversación.
        :return: Identificador del hilo creado.
        """
        thread = self.project.agents.threads.create()
        print(f"Created thread, ID: {thread.id}")
        return thread.id
        
    def get_project(self):
        return self.project

    def get_agent(self) -> Agent:
        """
        Obtiene el agente configurado en el provider.
        :return: Instancia del agente.
        """
        agent = self.project.agents.get_agent(os.environ["AGENT_NAME"])
        if not agent:
            raise ValueError(f"Agent with name {os.environ['AGENT_NAME']} not found.")
        logger.info(f"Using agent: {agent.name} (ID: {agent.id})")
        return agent