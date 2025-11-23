import logging
from fastapi import FastAPI
from app.routers import telegram, admin
from app.config import settings

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(title="Fitness Challenge Bot")

app.include_router(telegram.router)
app.include_router(admin.router)

@app.get("/")
def health_check():
    return {"status": "ok", "version": "0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

