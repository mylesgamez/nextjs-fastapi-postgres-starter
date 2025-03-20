import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db_engine import engine
from ..models import User

router = APIRouter()
logger = logging.getLogger(__name__)

class UserRead(BaseModel):
    id: int
    name: str

@router.get("/me", response_model=UserRead)
async def get_my_user():
    """
    Return the single seeded user, or 404 if not found.
    """
    logger.debug("GET /users/me called.")
    async with AsyncSession(engine) as session:
        async with session.begin():
            result = await session.execute(select(User))
            user = result.scalars().first()
            if not user:
                logger.warning("No user found in DB.")
                raise HTTPException(status_code=404, detail="User not found")
            logger.debug(f"Returning user: {user.id}, {user.name}")
            return UserRead(id=user.id, name=user.name)
