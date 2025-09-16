# app.py — BioFlow API (username-based auth, /jobs list, /jobs/{id} download)
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import os, shutil, datetime, uuid
from fastapi import FastAPI
from app.utils import (
    load_data,
    save_dataframe_to_csv,
    validate_data,
    clean_data,
    compute_diff,
    plot_volcano
)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, BioFlow API is running!"}
# 從 db.py 匯入
from app.db import (
    SessionLocal, init_db, get_db,
    User, Job, hash_password, verify_password,
    create_access_token, decode_token
)

app = FastAPI(title="BioFlow API", version="0.3.4", debug=True)

# ★ 每位使用者最多保留幾筆任務
MAX_JOBS_PER_USER = 20

# ✅ 啟動時初始化
@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    print("✅ Database initialized and folders ready.")

# ----------------- Security / helpers -----------------
security = HTTPBearer()

def current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload["sub"]  # 用 username（和 auth.py / Streamlit 對齊）
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def _delete_job_files(job: Job):
    """安全刪除與任務相關的檔案"""
    for p in (job.result_path, job.plot_path, job.upload_path):
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

def enforce_user_quota(db: Session, user_id: int, keep: int = MAX_JOBS_PER_USER):
    """
    只保留使用者最近 keep 筆；較舊的自動刪除（含檔案）
    在 /upload-csv/ 成功後呼叫。
    """
    q = (db.query(Job)
         .filter(Job.user_id == user_id)
         .order_by(Job.created_at.desc()))
    jobs = q.all()
    for j in jobs[keep:]:
        _delete_job_files(j)
        db.delete(j)
    db.commit()

# ----------------- Health -----------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------- （可保留）內建 Auth（若你用獨立 auth.py 可忽略） -----------------
@app.post("/auth/register")
def register(username: str, password: str, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already registered")
    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return {"message": "registered"}

@app.post("/auth/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# ----------------- 上傳 + 分析 -----------------
@app.post("/upload-csv/")
async def upload_csv(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="只接受 .csv 檔案")

    upload_path = os.path.join("uploads", file.filename)
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job_uid = str(uuid.uuid4())
    job = Job(job_id=job_uid, status="queued", upload_path=upload_path, user_id=user.id)
    db.add(job)
    db.commit()

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

        result_df, summary = compute_diff(df_clean)

        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        result_filename = f"result_{ts}.csv"
        result_path = os.path.join("results", result_filename)
        save_dataframe_to_csv(result_df, result_path)

        plot_filename = f"volcano_{ts}.png"
        plot_path = os.path.join("results", plot_filename)
        plot_volcano(result_df, plot_path)

        # 更新 Job（finished）
        job.status = "finished"
        job.summary = summary
        job.result_path = result_path
        job.plot_path = plot_path
        db.commit()

        # ✅ 配額控制：只保留最近 MAX_JOBS_PER_USER 筆
        enforce_user_quota(db, user.id, keep=MAX_JOBS_PER_USER)

        return {"job_id": job_uid, "status": "queued"}

    except HTTPException:
        raise
    except Exception as e:
        job.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"分析時發生錯誤: {e}")

# ----------------- 歷史任務（清單） -----------------
@app.get("/jobs")
def my_jobs(
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    jobs = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .all()
    )
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

# ----------------- 單筆 job 查詢 / 下載 -----------------
@app.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    download: Optional[bool] = Query(default=False),
    kind: Optional[str] = Query(default=None, pattern="^(result|plot)$"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    j = db.query(Job).filter(Job.job_id == job_id, Job.user_id == user.id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    if download:
        target: Optional[str] = None
        if kind == "result":
            target = j.result_path
        elif kind == "plot":
            target = j.plot_path
        if not target:
            raise HTTPException(status_code=404, detail="檔案尚未產生")
        if not os.path.exists(target):
            raise HTTPException(status_code=404, detail="檔案不存在")
        return FileResponse(target, media_type="application/octet-stream",
                            filename=os.path.basename(target))

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

# ----------------- 刪除任務（含檔案） -----------------
@app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    j = db.query(Job).filter(Job.job_id == job_id, Job.user_id == user.id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    _delete_job_files(j)
    db.delete(j)
    db.commit()
    return  # 204 No Content

# ----------------- 以檔名下載 -----------------
@app.get("/results/{filename}")
def get_result(
    filename: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    jobs = db.query(Job).filter(Job.user_id == user.id).all()

    candidate_paths = []
    for job in jobs:
        if job.result_path and os.path.basename(job.result_path) == filename:
            candidate_paths.append(job.result_path)
        if job.plot_path and os.path.basename(job.plot_path) == filename:
            candidate_paths.append(job.plot_path)

    if not candidate_paths:
        raise HTTPException(status_code=404, detail="找不到你的檔案")

    path = candidate_paths[0]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="檔案不存在")

    return FileResponse(path, media_type="application/octet-stream", filename=filename)
