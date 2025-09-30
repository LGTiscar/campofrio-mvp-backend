from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.domain.models.ChatRequest import ChatRequest
from src.application.ChatWithAgentUseCase import ChatWithAgentUseCase
from src.application.CreateNewThreadUseCase import CreateNewThreadUseCase
from src.infrastructure.fabric.FabricAgentService import FabricAgentService
import logging
import sys
import json



app = FastAPI()
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

@app.put("/thread/fabric/{old_thread_id}")
def create_thread_fabric(old_thread_id: str):
    """
    Elimina el hilo antiguo y crea uno nuevo.
    Devuelve el thread_id para mantener el contexto.
    Ejemplo de respuesta:
    {
        "thread_id": "abc123"
    }
    """
    fabric_service = FabricAgentService()
    try:
        thread_id = CreateNewThreadUseCase(fabric_service).execute(old_thread_id=old_thread_id)
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

@app.post("/chat/fabric/dax")
async def get_dax_queries(request: Request):
    payload = await request.json()
    thread_id = payload.get("thread_id")
    message = payload.get("message")
    assistant_id = payload.get("assistant_id", None)
    logger.info(f"Received user request: thread_id={thread_id}, message={message}, assistant_id={assistant_id}")

    fabric_service = FabricAgentService(assistant_id)

    if not thread_id or not message:
        return JSONResponse({"error": "thread_id and message are required"}, status_code=400)

    try:
        result = fabric_service.get_DAX_query(thread_id, message)
        return JSONResponse(content={"analysis result": result}, status_code=200)
    except Exception as e:
        return JSONResponse({f"Server error {e}"}, status_code=400)