"""quota – Gratis-Kontingent-Status (fuer Sidebar-Balken und Preise-Screen)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_student
from ..models import User
from ..schemas import QuotaOut
from ..services import quota as quota_service

router = APIRouter(prefix="/api/quota", tags=["quota"])


@router.get("", response_model=QuotaOut)
def get_quota(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return QuotaOut(**quota_service.quota_state(db, user))
