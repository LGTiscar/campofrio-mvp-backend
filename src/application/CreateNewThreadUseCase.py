from src.application.UseCase import UseCase

class CreateNewThreadUseCase(UseCase):
    def __init__(self, chat_service):
        self.chat_service = chat_service

    def execute(self, old_thread_id: str) -> str:
        """
        Crea un nuevo hilo de conversación.
        :return: Identificador del hilo creado.
        """
        thread_id = self.chat_service.create_thread(old_thread_id)
        return thread_id