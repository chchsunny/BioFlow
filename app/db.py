# db.py — SQLAlchemy models + JWT + helpers
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.engine import make_url
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt
import os
import sqlite3
import shutil

# ========= 基本設定 =========
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/bioflow.db")
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_TO_A_RANDOM_SECRET")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# ========= SQLite =========
try:
    url = make_url(DATABASE_URL)
except Exception:
    url = None

if url and url.drivername.startswith("sqlite"):
    # 解析出實際的 db 檔路徑
    db_path = url.database  # 例如 /app/data/bioflow.db
    if db_path:
        db_dir = os.path.dirname(db_path)

        # 1) 確保資料夾存在
        os.makedirs(db_dir, exist_ok=True)

        # 2) 若有人誤把 /app/bioflow.db 建成資料夾，自動移除
        wrong_dir = "/app/bioflow.db"
        if os.path.isdir(wrong_dir):
            try:
                shutil.rmtree(wrong_dir)
            except Exception:
                pass

        # 3) 若檔案不存在就先建立一顆空 DB
        if not os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.close()
            except Exception:
                pass

        # 4) 嘗試放寬權限
        for p in (db_dir, db_path):
            try:
                os.chmod(p, 0o777 if os.path.isdir(p) else 0o666)
            except Exception:
                pass

# ========= SQLAlchemy 基礎 =========

# 設定 SQLite 參數
connect_args = {}
if url and url.drivername.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 建立資料庫Engine (負責連線)
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# 建立 Session (操作資料庫用)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 支援多演算法
pwd_context = CryptContext(
    schemes=["argon2", "pbkdf2_sha256", "bcrypt"],
    deprecated="auto",
)

# ========= 資料表 =========

# User 表
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)  # 用 username
    hashed_password = Column(String, nullable=False)

    jobs = relationship("Job", back_populates="user")

# job 表
class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="queued", nullable=False)
    summary = Column(Text, nullable=True)

    upload_path = Column(String, nullable=True)
    result_path = Column(String, nullable=True)
    plot_path = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="jobs")

# ========= 初始化 =========
def init_db():
    Base.metadata.create_all(bind=engine)

# ========= 密碼/Token =========

# 參數設定
MAX_PASSWORD_BYTES = 256

# 檢查密碼是否合格
def _ensure_password_ok(pw: str) -> None:
    if not pw:
        raise ValueError("密碼不可為空")
    if len(pw.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("密碼過長，請縮短（上限約 256 bytes）")

# 雜湊密碼
def hash_password(pw: str) -> str:
    _ensure_password_ok(pw)
    return pwd_context.hash(pw)

# 驗證密碼
def verify_password(plain: str, hashed: str) -> bool:
    _ensure_password_ok(plain)
    return pwd_context.verify(plain, hashed)

# 檢查舊密碼是否需要更新
def password_needs_update(hashed: str) -> bool:
    """可用於登入成功後檢查是否要把舊雜湊升級為 argon2。"""
    try:
        return pwd_context.needs_update(hashed)
    except Exception:
        return False

# 建立 JWT Token
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# 解碼 JWT Token
def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None

# ========= Session  =========
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
