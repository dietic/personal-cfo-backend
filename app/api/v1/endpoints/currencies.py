from fastapi import APIRouter
from typing import List

router = APIRouter()

@router.get("", response_model=List[str])
async def get_currencies():
    """
    Get list of supported currencies
    """
    return ["USD", "PEN", "EUR"]
