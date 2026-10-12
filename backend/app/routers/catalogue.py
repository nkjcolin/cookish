from typing import Annotated

from fastapi import APIRouter, Query

from app.auth import User
from app.schemas.catalogue import IngredientSearchResult
from app.services import catalogue

router = APIRouter(tags=["catalogue"])


@router.get("/ingredients")
def search_ingredients(
    user: User,
    q: Annotated[str, Query(min_length=1, max_length=50)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> IngredientSearchResult:
    return catalogue.search_ingredients(q, limit)
