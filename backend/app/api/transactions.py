"""Transaction routes. PATCH is stubbed until F3-T04 fills filters and overrides."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_not_maintenance
from app.api.errors import ApiError
from app.db.models import User

router = APIRouter()


@router.patch("/transactions/{txn_id}", dependencies=[Depends(require_not_maintenance)])
def patch_transaction(
    txn_id: int,
    user: User = Depends(get_current_user),
) -> None:
    raise ApiError(404, "not_found", "Kayıt bulunamadı")
