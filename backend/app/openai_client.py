import logging
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY:
    logger.warning("No OPENAI_API_KEY found; GPT calls will fail.")
    client = None
else:
    client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI client created successfully.")
