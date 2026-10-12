from typing import Annotated
from uuid import UUID

from fastapi import Header

# Required on every request that changes inventory. The client generates one per user
# action and reuses it on retry, so a repeated tap never applies the change twice.
IdempotencyKey = Annotated[UUID, Header(alias="Idempotency-Key")]
