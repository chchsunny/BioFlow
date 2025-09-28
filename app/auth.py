# auth.py  — FastAPI 最小可用登入/註冊 + JWT
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt

# ===== 基本設定：JWT 與資料庫 =====
SECRET_KEY = "CHANGE_ME_TO_A_RANDOM_SECRET"
ALGORITHM = "HS256"                    
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# SQLite 資料庫連線 
SQLALCHEMY_DATABASE_URL = "sqlite:///./bioflow.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 密碼設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 建立資料庫連線
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===== 資料表 =====
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

# ===== Pydantic =====
class RegisterReq(BaseModel):
    username: str
    password: str

class TokenResp(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ===== 工具 =====
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

# ===== App =====
app = FastAPI(title="Auth API")

@app.post("/auth/register", status_code=201)
def register(req: RegisterReq, db: Session = Depends(get_db)):
    if not req.username or not req.password:
        raise HTTPException(400, "username/password required")
    exists = db.query(User).filter(User.username == req.username).first()
    if exists:
        raise HTTPException(409, "username already exists")
    user = User(username=req.username, hashed_password=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username}

@app.post("/auth/login", response_model=TokenResp)
def login(req: RegisterReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    token = create_access_token({"sub": req.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@app.get("/health")
def health():
    return {"ok": True}
