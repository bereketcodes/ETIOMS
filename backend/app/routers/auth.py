import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.organization import OrganizationProfile
from backend.app.models.organization_invite import OrganizationInvite
from backend.app.models.users import User
from backend.app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    validate_jwt_configuration,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=255)
    user_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    invitation_code: str | None = Field(default=None, min_length=20, max_length=128)

    @model_validator(mode="after")
    def require_company_or_invitation(self):
        has_company = bool(self.company_name and self.company_name.strip())
        has_invitation = bool(self.invitation_code and self.invitation_code.strip())
        if has_company == has_invitation:
            raise ValueError("Provide either a company name or an invitation code.")
        return self

    @field_validator("company_name")
    @classmethod
    def trim_company_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("user_name")
    @classmethod
    def trim_user_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    user_name: str
    organization_id: str


class InvitationResponse(BaseModel):
    invitation_code: str
    expires_at: datetime


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    validate_jwt_configuration()
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    if request.invitation_code:
        now = datetime.now(timezone.utc)
        code_hash = hashlib.sha256(request.invitation_code.encode("utf-8")).hexdigest()
        invitation = db.query(OrganizationInvite).filter(
            OrganizationInvite.code_hash == code_hash,
            OrganizationInvite.used_at.is_(None),
            OrganizationInvite.expires_at > now,
        ).first()
        if invitation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation code is invalid, expired, or already used.",
            )
        organization_id = invitation.organization_id
        claim = db.execute(
            update(OrganizationInvite)
            .where(
                OrganizationInvite.id == invitation.id,
                OrganizationInvite.used_at.is_(None),
                OrganizationInvite.expires_at > now,
            )
            .values(used_at=now)
            .execution_options(synchronize_session=False)
        )
        if claim.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation code is invalid, expired, or already used.",
            )
    else:
        if request.company_name is None:
            raise HTTPException(status_code=422, detail="Company name is required.")
        organization = OrganizationProfile(company_name=request.company_name)
        db.add(organization)
        db.flush()
        organization_id = organization.id

    user = User(
        email=request.email,
        user_name=request.user_name.strip(),
        hashed_password=hash_password(request.password),
        organization_id=organization_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if db.query(User).filter(User.email == request.email).first():
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            ) from exc
        raise

    db.refresh(user)
    return _token_response(user)


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationResponse:
    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    invitation = OrganizationInvite(
        code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
        organization_id=current_user.organization_id,
        created_by_user_id=current_user.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    db.commit()
    return InvitationResponse(invitation_code=code, expires_at=expires_at)


@router.post("/token", response_model=TokenResponse)
def login(
    credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    validate_jwt_configuration()
    email = credentials.username.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active or not verify_password(
        credentials.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_response(user)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        user_name=current_user.user_name,
        organization_id=str(current_user.organization_id),
    )
