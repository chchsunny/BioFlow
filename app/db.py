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

# ========= SQLite 自動防呆（只在 sqlite:// 才執行）=========
try:
    url = make_url(DATABASE_URL)
except Exception:
    # 若 URL 解析失敗，就當作一般字串；後續交給 SQLAlchemy 報錯
    url = None

if url and url.drivername.startswith("sqlite"):
    # 解析出實際的 db 檔路徑
    db_path = url.database  # 例如 /app/data/bioflow.db
    if db_path:
        db_dir = os.path.dirname(db_path)

        # 1) 確保資料夾存在
        os.makedirs(db_dir, exist_ok=True)

        # 2) 若有人誤把 /app/bioflow.db 建成「資料夾」，自動移除
        wrong_dir = "/app/bioflow.db"
        if os.path.isdir(wrong_dir):
            try:
                shutil.rmtree(wrong_dir)
            except Exception:
                pass

        # 3) 若檔案不存在就先建立一顆空 DB（避免 "unable to open database file"）
        if not os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.close()
            except Exception:
                # 若建立失敗也不擋住後續，讓 SQLAlchemy 報更完整的錯
                pass

        # 4) 嘗試放寬權限（Windows 掛載時仍以主機為準；在 Linux 容器有效）
        for p in (db_dir, db_path):
            try:
                os.chmod(p, 0o777 if os.path.isdir(p) else 0o666)
            except Exception:
                pass

# ========= SQLAlchemy 基礎 =========
connect_args = {}
if url and url.drivername.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ========= 資料表 =========
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)  # 用 username
    hashed_password = Column(String, nullable=False)

    jobs = relationship("Job", back_populates="user")

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
def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None

# ========= Session 依賴 =========
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
