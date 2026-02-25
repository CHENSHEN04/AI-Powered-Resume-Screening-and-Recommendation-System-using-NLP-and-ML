
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os

# Initialize FastAPI App
app = FastAPI(
    title="Resume AI Screening API",
    description="Backend for AI-Powered Resume Screening & Recommendation System",
    version="2.0.0"
)

# CORS Configuration
origins = [
    "http://localhost:3000",  # Next.js Frontend
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---

@app.get("/")
async def root():
    return {"message": "Resume AI Backend is Running", "version": "2.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}


from backend.routers import analyze, chat, history, profile

app.include_router(analyze.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(profile.router)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
