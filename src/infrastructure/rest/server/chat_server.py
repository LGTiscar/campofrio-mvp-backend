from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.domain.models.ChatRequest import ChatRequest
from src.application.ChatWithAgentUseCase import ChatWithAgentUseCase
from src.application.CreateNewThreadUseCase import CreateNewThreadUseCase
from src.infrastructure.azure.AzureFoundryAgentService import AzureFoundryAgentService
import logging
import sys
import json

from src.infrastructure.azure.AzureFoundryAgentService import AzureFoundryAgentService
from src.infrastructure.fabric.FabricAgentService import FabricAgentService

app = FastAPI()
service = AzureFoundryAgentService()

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

app = FastAPI(
    title="Camp Chat Backend",
    description="API REST para chat con agente Azure",
    version="1.0.0"
)

# TODO: ojo a esto cuando azure
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS" , "GET"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """
    Endpoint de bienvenida.
    """
    return {"message": "Backend del Agente Campofrío"}

@app.post("/chat/stream")
async def chat_stream(request: Request):
    payload = await request.json()
    thread_id = payload.get("thread_id")
    message = payload.get("message")
    logger.info(f"Received streaming chat request: thread_id={thread_id}, message={message}")

    if not thread_id or not message:
        return JSONResponse({"error": "thread_id and message are required"}, status_code=400)

    try:
        def event_stream():
            for evt in service.chat_stream(thread_id, message):
                data = json.dumps(evt)
                yield f"data: {data}\n\n"
            # final event
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    
    except Exception as e:

        return JSONResponse({"error": "Server error, probabily reached quota limit"}, status_code=400)

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
    logger.info(f"Received chat request: thread_id={request.thread_id}, message={request.message}")

    response = ChatWithAgentUseCase(service).execute(request.thread_id, request.message)
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
    try:
        thread_id = CreateNewThreadUseCase(service).execute()
        return JSONResponse(content={"thread_id": thread_id}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/thread/fabric")
def create_thread_fabric():
    """
    Crea un nuevo hilo/conversación con el agente.
    Devuelve el thread_id para mantener el contexto.
    Ejemplo de respuesta:
    {
        "thread_id": "abc123"
    }
    """
    fabric_service = FabricAgentService()
    try:
        thread_id = CreateNewThreadUseCase(fabric_service).execute()
        return JSONResponse(content={"thread_id": thread_id}, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/chat/fabric/stream")
async def chat_stream_fabric(request: Request):
    payload = await request.json()
    thread_id = payload.get("thread_id")
    message = payload.get("message")
    assistant_id = payload.get("assistant_id", None)
    logger.info(f"Received streaming chat request: thread_id={thread_id}, message={message}, assistant_id={assistant_id}")

    fabric_service = FabricAgentService(assistant_id)

    if not thread_id or not message:
        return JSONResponse({"error": "thread_id and message are required"}, status_code=400)

    try:
        async def event_stream_fabric():
            async for evt in fabric_service.chat_stream(thread_id, message):
                data = json.dumps(evt)
                yield f"data: {data}\n\n"
            # final event
            yield "event: done\ndata: {}\n\n"
            
        return StreamingResponse(event_stream_fabric(), media_type="text/event-stream")
    
    except Exception as e:

        return JSONResponse({"error": "Server error, probabily reached quota limit"}, status_code=400)