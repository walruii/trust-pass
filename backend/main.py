from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Allow requests from your Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define expected JSON request payload
class PromptRequest(BaseModel):
    prompt: str
    temperature: float = 0.7

@app.get("/hello_world")
async def hello_world():
  return {"message": "hello world!"}

@app.post("/api/predict")
async def predict(data: PromptRequest):
    # Pass data.prompt to your local model or AI API here
    result = f"Model generated response for: '{data.prompt}'"
    return {"status": "success", "response": result}
