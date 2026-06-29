"""
User integrations API — connect/disconnect a GitHub account (PAT, stored encrypted).

Auth-required; operates on the current user only. The PAT is validated against the
GitHub API, then stored ENCRYPTED (auth/crypto.py). The token is NEVER returned.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.crypto import encrypt
from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from integrations import github_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/me/integrations", tags=["integrations"])


class GitHubTokenRequest(BaseModel):
    token: str


def _load_user(db: Session, current_user: User) -> User:
    """Re-load the user on the request's DB session so writes persist."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/github")
def connect_github(
    req: GitHubTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    token = (req.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")
    try:
        login = github_client.validate_token(token)
    except ValueError:
        # ponytail: never echo the token or the upstream error verbatim.
        raise HTTPException(status_code=400, detail="Invalid GitHub token")

    user = _load_user(db, current_user)
    user.github_token_enc = encrypt(token)  # stored ENCRYPTED, never plaintext
    user.github_login = login
    db.commit()
    return {"connected": True, "login": login}


@router.delete("/github")
def disconnect_github(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    user = _load_user(db, current_user)
    user.github_token_enc = None
    user.github_login = None
    db.commit()
    return {"connected": False}
