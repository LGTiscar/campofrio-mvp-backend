from src.application.UseCase import UseCase

class CreateNewThreadUseCase(UseCase):
    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def execute(self, old_thread_id: str) -> str:
        """
        Crea un nuevo hilo de conversación.
        :return: Identificador del hilo creado.
        """
        thread_id = self.llm_provider.create_thread(old_thread_id)
        return thread_id