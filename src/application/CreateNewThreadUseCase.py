from src.application.UseCase import UseCase

class CreateNewThreadUseCase(UseCase):
    def __init__(self, chat_service):
        self.chat_service = chat_service

    def execute(self) -> str:
        """
        Crea un nuevo hilo de conversación.
        :return: Identificador del hilo creado.
        """
        thread_id = self.chat_service.create_thread()
        return thread_id