import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.seed import seed_user_if_needed
from app.routers.chat import router as chat_router
from app.routers.user import router as user_router

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI()

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Seed DB once on startup
    seed_user_if_needed()

    # Include our routers
    app.include_router(user_router, prefix="/users", tags=["users"])
    app.include_router(chat_router, tags=["chat"])

    return app

app = create_app()

if OPENAI_API_KEY:
    logger.info(f"OPENAI_API_KEY found (length={len(OPENAI_API_KEY)}).")
else:
    logger.warning("No OPENAI_API_KEY found. GPT calls will fail (fallback).")
