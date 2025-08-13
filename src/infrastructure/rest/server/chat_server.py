from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from src.domain.models.ChatRequest import ChatRequest
from src.application.ChatWithAgentUseCase import ChatWithAgentUseCase
from src.application.CreateNewThreadUseCase import CreateNewThreadUseCase
from src.infrastructure.azure.AzureFoundryAgentService import AzureFoundryAgentService

app = FastAPI(
    title="Camp Chat Backend",
    description="API REST para chat con agente Azure",
    version="1.0.0"
)

@app.get("/")
async def root():
    """
    Endpoint de bienvenida.
    """
    return {"message": "Backend del Agente Campofrío"}

def get_azure_chat_service():
    return AzureFoundryAgentService()

@app.post("/chat")
def chat_with_agent(request: ChatRequest):
    """
    Envía un mensaje al agente conversacional de Azure y recibe la respuesta.
    - thread_id: ID del hilo/conversación.
    - message: Mensaje del usuario.
    Ejemplo de request:
    {
        "thread_id": "abc123",
        "message": "Hola, ¿cómo estás?"
    }
    """
    azure_chat_service = get_azure_chat_service()
    response = ChatWithAgentUseCase(azure_chat_service).execute(request.thread_id, request.message)
    return JSONResponse(content=response.agent_reply, status_code=200)

@app.post("/thread")
def create_thread():
    """
    Crea un nuevo hilo/conversación con el agente.
    Devuelve el thread_id para mantener el contexto.
    Ejemplo de respuesta:
    {
        "thread_id": "abc123"
    }
    """
    azure_chat_service = get_azure_chat_service()
    try:
        thread_id = CreateNewThreadUseCase(azure_chat_service).execute()
        return JSONResponse(content={"thread_id": thread_id}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))