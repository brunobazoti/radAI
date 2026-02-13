import logging

from fastapi import FastAPI

from app.routers import webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="WhatsApp Flight Tracker",
    version="0.1.0",
    description="Bot de WhatsApp para rastreamento de voos em tempo real.",
)

app.include_router(webhook.router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
