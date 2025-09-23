from src.domain.providers.LLMProvider import LLMProvider
from src.domain.exceptions.AgentCreationException import AgentCreationException
from src.infrastructure.SingletonMeta import SingletonMeta
from azure.identity import DefaultAzureCredential
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

# Optional: Load from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
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

            # Create credential for interactive authentication
            self.credential = DefaultAzureCredential(managed_identity_client_id="luisgtiscar@pospotential.com")
            
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
            logger.debug("🔄 Refreshing authentication token...")
            if self.credential is None:
                raise ValueError("No credential available")
            self.token = self.credential.get_token("https://api.fabric.microsoft.com/.default")
            logger.debug(f"✅ Token obtained, expires at: {time.ctime(self.token.expires_on)}")
            
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
                model="gpt-5", 
                top_p=0.6)
            logger.info(f"✅ Agent created with ID: {agent.id}")
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