from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token
from app.database import get_db
from app.models.organisation import Organisation
from app.models.user import User, UserRole
from app.schemas.schemas import UserCreate, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organisation(name=payload.org_name)
    db.add(org)
    db.flush()  # get org.id before creating the user

    user = User(org_id=org.id, email=payload.email, password_hash=hash_password(payload.password), role=UserRole.owner)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.org_id, user.role.value)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id, user.org_id, user.role.value)
    return TokenResponse(access_token=token)
