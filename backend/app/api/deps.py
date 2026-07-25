from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from database import get_db
from security import get_current_user


def get_current_db_user(
    token_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the JWT subject to a real, persisted User row."""
    user = UserRepository(db).get_by_username(token_payload.get("sub"))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_organization_id(user: User = Depends(get_current_db_user)) -> int:
    """The authenticated caller's tenant, for scoping mutate/delete operations."""
    return user.organization_id
