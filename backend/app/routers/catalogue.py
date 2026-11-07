from typing import Annotated
from uuid import UUID

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
    ingredient_id: Annotated[
        UUID | None,
        Query(description="Resolve this catalogue ID exactly, ignoring q when supplied."),
    ] = None,
) -> IngredientSearchResult:
    return catalogue.search_ingredients(q, limit, ingredient_id=ingredient_id)
