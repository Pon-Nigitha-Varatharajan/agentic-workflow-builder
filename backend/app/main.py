from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from app.llm_unbound import call_llm, UnboundError
from app.routers import workflows, runs
from app.db import Base, engine

# ------------------------
# Allowed models (hackathon)
# ------------------------
ALLOWED_MODELS = {
    "kimi-k2p5",
    "kimi-k2-instruct-0905",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Create DB tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Agentic Workflow Builder", lifespan=lifespan)

# ✅ CORS: fixes Swagger "Failed to fetch" + enables frontend polling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for hackathon/dev; tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include routers ONCE (no duplicate)
app.include_router(workflows.router)
app.include_router(runs.router)


class DebugLLMRequest(BaseModel):
    model: str = Field(..., examples=["kimi-k2p5"])
    prompt: str = Field(..., examples=["Say hello in one sentence."])


class DebugLLMResponse(BaseModel):
    response: str
    usage: dict = {}


@app.get("/")
def root():
    return {"status": "Agentic Workflow Builder API running"}


@app.post("/debug/llm", response_model=DebugLLMResponse)
async def debug_llm(req: DebugLLMRequest):
    if req.model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model '{req.model}'. Choose from: {', '.join(sorted(ALLOWED_MODELS))}",
        )

    try:
        text, usage = await call_llm(model=req.model, prompt=req.prompt)
        return DebugLLMResponse(response=text, usage=usage)
    except UnboundError as e:
        raise HTTPException(status_code=502, detail=str(e))