import uvicorn
from src.infrastructure.rest.server.chat_server import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)