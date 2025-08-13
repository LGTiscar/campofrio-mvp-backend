from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def __init__(self):
        pass
    @abstractmethod
    def get_project(self):
        pass
    @abstractmethod
    def get_agent(self):
        pass