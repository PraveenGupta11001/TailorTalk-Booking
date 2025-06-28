from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from app.agent import run_agent
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.187.96:8501", 'https://tailortalk-booking.streamlit.app'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    responses: list[str]

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    responses = run_agent(request.message)
    return ChatResponse(responses=responses)