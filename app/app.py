"""
BioFlow API 主程式
功能：
- 使用者註冊 / 登入 (JWT)
- 上傳 CSV 並進行基因差異分析
- 管理分析任務 (查詢、刪除、下載結果/圖表)
- 健康檢查 (health check)
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import os, shutil, datetime, uuid

from app.utils import (
    load_data,
    save_dataframe_to_csv,
    validate_data,
    clean_data,
    compute_diff,
    plot_volcano
)

# 從 db.py 匯入
from app.db import (
    SessionLocal, init_db, get_db,
    User, Job, hash_password, verify_password,
    create_access_token, decode_token
)

# ========= FastAPI 初始化 =========
app = FastAPI(title="BioFlow API", version="0.3.4", debug=True)

# 啟用 CORS：顯式允許常見本機前端來源，避免瀏覽器阻擋
_default_origins = (
    os.getenv("CORS_ORIGINS")
    or "http://localhost:5500,http://127.0.0.1:5500,"
       "http://localhost:3000,http://127.0.0.1:3000,"
       "http://localhost:5173,http://127.0.0.1:5173,"
       "http://localhost:8501"
)
ALLOW_ORIGINS = [o.strip() for o in _default_origins.split(",") if o.strip()]

# 只在需要時啟用 CORS（同源提供 /web 時預設不啟用，避免中介層錯誤）
if os.getenv("ENABLE_CORS", "false").lower() == "true":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 提供前端靜態檔（同源開發：避免 CORS）
app.mount("/web", StaticFiles(directory="frontend", html=True), name="web")

# ========= 常數設定 =========
MAX_JOBS_PER_USER = 20  # 每位使用者最多保留幾筆任務

# ========= 啟動時初始化 =========
@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    print(" Database initialized and folders ready.")

# ========= 首頁 =========
@app.get("/")
def root():
    return {"message": "Welcome to BioFlow API", "version": "0.3.4"}

# ========= Security / helpers =========
security = HTTPBearer()

# 驗證目前使用者 (透過 JWT Token)
def current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload["sub"]
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# 刪除相關檔案
def _delete_job_files(job: Job):
    for p in (job.result_path, job.plot_path, job.upload_path):
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

# 只保留使用者最近的結果，較舊的自動刪除
def enforce_user_quota(db: Session, user_id: int, keep: int = MAX_JOBS_PER_USER):
    q = (db.query(Job)
         .filter(Job.user_id == user_id)
         .order_by(Job.created_at.desc()))
    jobs = q.all()
    for j in jobs[keep:]:
        _delete_job_files(j)
        db.delete(j)
    db.commit()

# ========= Health =========
@app.get("/health")
def health():
    return {"status": "ok"}

# ========= Auth =========

# JSON 請求模型
class AuthReq(BaseModel):
    username: str
    password: str

# 註冊
@app.post("/auth/register")
def register(username: str, password: str, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already registered")
    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return {"message": "registered"}

# 登錄
@app.post("/auth/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# GET 版（用於疑難排解與簡化 CORS）
@app.get("/auth/register")
def register_get(username: str, password: str, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already registered")
    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return {"message": "registered"}

@app.get("/auth/login")
def login_get(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# JSON 版註冊
@app.post("/auth/register-json")
def register_json(req: AuthReq, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=409, detail="Username already registered")
    user = User(username=req.username, hashed_password=hash_password(req.password))
    db.add(user)
    db.commit()
    return {"message": "registered"}

# JSON 版登入
@app.post("/auth/login-json")
def login_json(req: AuthReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# ========= 上傳 + 分析 =========

# 建立臨時資料夾
@app.post("/upload-csv/")
async def upload_csv(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):

# 上傳檔案檢查與儲存
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="只接受 .csv 檔案")

    upload_path = os.path.join("uploads", file.filename)
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

# 建立job
    job_uid = str(uuid.uuid4())
    job = Job(job_id=job_uid, status="queued", upload_path=upload_path, user_id=user.id)
    db.add(job)
    db.commit()

# 資料驗證與清理
    try:
        df = load_data(upload_path)
        if df is None or df.shape[0] == 0:
            job.status = "failed"
            db.commit()
            raise HTTPException(status_code=400, detail="檔案為空")

        vreport = validate_data(df)
        if vreport["missing_columns"]:
            job.status = "failed"
            db.commit()
            raise HTTPException(status_code=400, detail=f"缺少必要欄位: {', '.join(vreport['missing_columns'])}")

        df_clean = clean_data(df)
        if df_clean.shape[0] == 0:
            job.status = "failed"
            db.commit()
            raise HTTPException(status_code=400, detail="清理後資料為空")

# 差異分析與結果輸出
        result_df, summary = compute_diff(df_clean)

        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        result_filename = f"result_{ts}.csv"
        result_path = os.path.join("results", result_filename)
        save_dataframe_to_csv(result_df, result_path)

        plot_filename = f"volcano_{ts}.png"
        plot_path = os.path.join("results", plot_filename)
        plot_volcano(result_df, plot_path)

# 更新狀態
        job.status = "finished"
        job.summary = summary
        job.result_path = result_path
        job.plot_path = plot_path
        db.commit()

# 配額控制
        enforce_user_quota(db, user.id, keep=MAX_JOBS_PER_USER)

# 回傳結果
        return {"job_id": job_uid, "status": "queued"}

# 錯誤處理
    except HTTPException:
        raise
    except Exception as e:
        job.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"分析時發生錯誤: {e}")

# ========= 歷史清單 =========
@app.get("/jobs")
def my_jobs(
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    
# 查詢jobs
    jobs = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .all()
    )

# 回傳結果
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "summary": j.summary,
            "created_at": j.created_at.isoformat(),
            "result_path": j.result_path,
            "plot_path": j.plot_path,
            "result_filename": os.path.basename(j.result_path) if j.result_path else None,
            "plot_filename": os.path.basename(j.plot_path) if j.plot_path else None,
        }
        for j in jobs
    ]

# ========= 單筆job下載 =========
@app.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    download: Optional[bool] = Query(default=False),
    kind: Optional[str] = Query(default=None, pattern="^(result|plot)$"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    
# 查詢 Job
    j = db.query(Job).filter(Job.job_id == job_id, Job.user_id == user.id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

# 處理下載請求
    if download:
        target: Optional[str] = None
        if kind == "result":
            target = j.result_path
        elif kind == "plot":
            target = j.plot_path
        if not target or not os.path.exists(target):
            raise HTTPException(status_code=404, detail="檔案不存在")
        return FileResponse(target, media_type="application/octet-stream",
                            filename=os.path.basename(target))

# 回傳結果
    return {
        "job_id": j.job_id,
        "status": j.status,
        "summary": j.summary,
        "created_at": j.created_at.isoformat(),
        "result_path": j.result_path,
        "plot_path": j.plot_path,
        "result_filename": os.path.basename(j.result_path) if j.result_path else None,
        "plot_filename": os.path.basename(j.plot_path) if j.plot_path else None,
    }

# ========= 刪除job =========
@app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    
# 查詢job
    j = db.query(Job).filter(Job.job_id == job_id, Job.user_id == user.id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    
# 刪除檔案資料
    _delete_job_files(j)
    db.delete(j)
    db.commit()
    return  

# ========= 以檔名下載 =========
@app.get("/results/{filename}")
def get_result(
    filename: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    
# 從資料庫取出該使用者的所有job，找出符合檔名的結果檔或圖表檔
    jobs = db.query(Job).filter(Job.user_id == user.id).all()

    candidate_paths = []
    for job in jobs:
        if job.result_path and os.path.basename(job.result_path) == filename:
            candidate_paths.append(job.result_path)
        if job.plot_path and os.path.basename(job.plot_path) == filename:
            candidate_paths.append(job.plot_path)

 # 如果完全找不到符合的檔案回傳 404
    if not candidate_paths:
        raise HTTPException(status_code=404, detail="找不到你的檔案")

    path = candidate_paths[0]

# 如果檔案路徑存在於資料庫，但檔案本身已被刪除回傳 404
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="檔案不存在")

    return FileResponse(path, media_type="application/octet-stream", filename=filename)
