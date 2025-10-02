from src.domain.providers.LLMProvider import LLMProvider
from src.infrastructure.SingletonMeta import SingletonMeta
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


class AzureFoundryLlmProvider(LLMProvider, metaclass=SingletonMeta):
    def __init__(self):
        self.project = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint="https://campo-chatbot-ai-resource.services.ai.azure.com/api/projects/campo-chatbot-ai"
        )
        self.agent = self.project.agents.get_agent("asst_gZnjgryketWkdfaWPtAQmvUn")
    
    def get_project(self):
        return self.project
    
    def get_agent(self):
        return self.agent