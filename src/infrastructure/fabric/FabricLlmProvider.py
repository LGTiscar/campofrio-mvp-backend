from src.domain.providers.LLMProvider import LLMProvider
from src.domain.exceptions.AgentCreationException import AgentCreationException
from src.domain.exceptions.ThreadCreationException import ThreadCreationException
from src.infrastructure.SingletonMeta import SingletonMeta
from src.infrastructure.repositories.prompts.AgentSystemPrompt import AgentSystemPrompt
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
import time
import uuid
import logging
import sys
import warnings
from openai import OpenAI
from typing import Optional
import os

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

# Suppress OpenAI Assistants API deprecation warnings
# (Fabric Data Agents don't support the newer Responses API yet)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*Assistants API is deprecated.*"
)

try:
    load_dotenv()
    logger.info("✅ .env file loaded successfully.")
    # Don't log secrets; only log presence of expected vars
    logger.info(f"AZURE_CLIENT_ID present: {bool(os.getenv('AZURE_CLIENT_ID'))}")
except Exception as e:
    logger.warning(f"Could not load .env file: {e}")
    pass

class FabricLlmProvider(LLMProvider, metaclass=SingletonMeta):
    """
    Proveedor LLM para Azure Fabric Data Agent. Utiliza autenticación interactiva y maneja la renovación del token.
    Crea una instancia persistente del agente LLM configurado en Fabric Data Agent.
    Consulta instancias persistentes de agente LLM.
    """
    
    def __init__(self):
        """
        Initialize the Fabric Data Agent client.
        """
        self.data_agent_url = os.environ["FABRIC_DATA_AGENT_URL"]
        self.credential = None
        self.token = None
        
        self._authenticate()
    
    def _authenticate(self):
        """
        Perform interactive browser authentication and get initial token.
        """
        try:
            logger.info("\n🔐 Starting authentication...")

            # Create credential for authentication (DefaultAzureCredential will pick the appropriate flow)
            self.credential = DefaultAzureCredential()
            
            # Get initial token
            self._refresh_token()
            
            logger.info("✅ Authentication successful!")
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise
    
    def _refresh_token(self):
        """
        Refresh the authentication token.
        """
        try:
            logger.info("🔄 Refreshing authentication token...")
            if self.credential is None:
                raise ValueError("No credential available")
            self.token = self.credential.get_token("https://api.fabric.microsoft.com/.default")
            logger.info(f"✅ Token obtained, expires at: {time.ctime(self.token.expires_on)}")
            
        except Exception as e:
            logger.error(f"❌ Token refresh failed: {e}")
            raise

    def _get_openai_client(self) -> OpenAI:
        """
        Create an OpenAI client configured for Fabric Data Agent calls.
        
        Returns:
            OpenAI: Configured OpenAI client
        """
        # Check if token needs refresh (refresh 5 minutes before expiry)
        if self.token and self.token.expires_on <= (time.time() + 300):
            self._refresh_token()
        
        if not self.token:
            raise ValueError("No valid authentication token available")
        
        if not self.data_agent_url:
            raise ValueError("FABRIC_DATA_AGENT_URL environment variable is not set")
        
        return OpenAI(
            api_key="",  # Not used - we use Bearer token
            base_url=self.data_agent_url,
            default_query={"api-version": "2025-04-01-preview"},
            default_headers={
                "Authorization": f"Bearer {self.token.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "ActivityId": str(uuid.uuid4())
            }
        )
    
    def _create_agent(self):
        """
        Create a new Fabric Data Agent instance.
        
        Returns:
            agent: Configured Fabric Data Agent
        """
        client = self._get_openai_client()
        
        try:
            agent = client.beta.assistants.create(
                # TODO: esto no cambia nada en el asistente creado
                name="Campofrio Agent",
                model="gpt-5-nano-2025-08-07",
                instructions=AgentSystemPrompt().get_prompt(),
            )
            logger.info(f"✅ Agent created with ID: {agent.id}. {agent.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create agent: {e}")
            raise AgentCreationException(f"Failed to create agent: {e}")
        
        return agent
    
    def get_agent(self, assistant_id: Optional[str] = None):
        """
        Get a Fabric Data Agent already created instance by ID.
        
        Returns:
            agent: Configured Fabric Data Agent
        """
        client = self._get_openai_client()
        
        if assistant_id is None:
            agent = self._create_agent()
        else:
            try:
                agent = client.beta.assistants.retrieve(assistant_id=assistant_id)
                logger.info(f"✅ Agent retrieved with ID: {agent.id}")
            except Exception as e:
                logger.info(f"❌ Agent with ID {assistant_id} not found. {e}. Creating a new one...")
                agent = self._create_agent()
        
        return agent
        
    def get_project(self):
        return self._get_openai_client()

    def create_thread(self, old_thread_id: str) -> str:
        """
        Crea un nuevo hilo de conversación.
        Returns:
          thread_id: Identificador del hilo creado.
        """
        
        client = self.get_project()

        try:
            client.beta.threads.delete(thread_id=old_thread_id)
        except Exception as cleanup_error:
            print(f"⚠️ Warning: Thread cleanup failed: {cleanup_error}")
        try:
            thread_id = client.beta.threads.create().id
            logger.info(f"✅ Created thread, ID: {thread_id}")
        except Exception as e:
            logger.error(f"❌ Error creating thread, error: {e}")
            raise ThreadCreationException(f"Failed to create thread, error: {e}")
        return thread_id