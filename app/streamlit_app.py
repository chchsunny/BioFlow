import streamlit as st
import requests
import pandas as pd
import time
import os

# API 位置，優先讀環境變數，否則預設用 Docker Compose 的服務名稱 "api"
API_BASE = os.getenv("API_BASE", "http://api:8000")

# ========= 可調整區 =========
BACKEND = "http://api:8000"     # BioFlow API (app.py)
AUTH_BACKEND = "http://api:8000"  # Auth API (auth.py)
USE_FORM_LOGIN = False               
JOBS_MY_ENDPOINT = "/jobs"            
# ==========================

# 新增：頁面設定 + 初始化 token（避免 KeyError）
st.set_page_config(page_title="BioFlow", page_icon="🧬", layout="wide")
if "token" not in st.session_state:
    st.session_state["token"] = None

# ========= Sidebar: 登入/註冊 =========
st.sidebar.header("登入 / 註冊")

with st.sidebar.expander("登入", expanded=True):
    username = st.text_input("帳號 (username)", key="login_user")
    password = st.text_input("密碼", type="password", key="login_pwd")
    if st.button("登入", key="btn_login"):
        try:
            r = requests.post(f"{AUTH_BACKEND}/auth/login",
                              params={"username": username, "password": password},
                              timeout=30)
            if r.ok:
                data = r.json()
                token = data.get("access_token")
                if token:
                    st.session_state["token"] = token
                    st.success("登入成功")
                else:
                    st.error("登入成功但沒有回傳 token")
            else:
              
                try:
                    st.error(r.json().get("detail", r.text))
                except Exception:
                    st.error(r.text)
        except Exception as e:
            st.error(f"登入錯誤：{e}")

with st.sidebar.expander("註冊新帳號"):
    reg_user = st.text_input("帳號 (username)", key="reg_user")
    reg_pwd = st.text_input("密碼 (註冊)", type="password", key="reg_pwd")
    if st.button("註冊", key="btn_register"):
        try:
            r = requests.post(f"{AUTH_BACKEND}/auth/register",
                              params={"username": reg_user, "password": reg_pwd},
                              timeout=30)
            if r.ok:
                st.success("註冊成功，請到上方登入")
            else:
                try:
                    st.error(r.json().get("detail", r.text))
                except Exception:
                    st.error(r.text)
        except Exception as e:
            st.error(f"註冊錯誤：{e}")

st.sidebar.write("---")

# 修改：安全取得 token，避免直接索引造成 KeyError
token = st.session_state.get("token")
is_logged_in = token is not None

if is_logged_in:
    if st.sidebar.button("登出", key="btn_logout"):
        st.session_state["token"] = None
        st.experimental_rerun()

# ========= 主畫面 =========
st.title("🧬 BioFlow - 分析面板")

if not is_logged_in:
    st.info("目前為未登入狀態。你仍可看到介面，但操作按鈕會被停用。")

# 修改：用 token 建 headers
headers = {"Authorization": f"Bearer {token}"} if is_logged_in else {}

# ========= 上傳與分析 =========
with st.expander("上傳 CSV 並執行分析", expanded=True):
    up = st.file_uploader("選擇 CSV 檔", type=["csv"], key="uploader_csv")
    start_disabled = (not is_logged_in) or (up is None)
    if st.button("開始分析", key="btn_start_analysis", disabled=start_disabled):
        try:
            files = {"file": (up.name, up.getvalue(), "text/csv")}
            r = requests.post(f"{BACKEND}/upload-csv/", files=files, headers=headers, timeout=120)
            if r.ok:
                job_id = r.json().get("job_id")
                if not job_id:
                    st.error("後端未回傳 job_id，請確認 /upload-csv/ 的回應格式。")
                else:
                    st.success(f"任務建立成功：{job_id}")
                    status_box = st.empty()
                    with st.spinner("分析中…"):
                        while True:
                            jr = requests.get(f"{BACKEND}/jobs/{job_id}", headers=headers, timeout=30)
                            if not jr.ok:
                                status_box.error(jr.text)
                                break
                            data = jr.json()
                            status = data.get("status", "unknown")
                            status_box.write(f"當前狀態：{status}")
                            if status in ("finished", "failed"):
                                if status == "finished":
                                    st.success("分析完成！")
                                    if "summary" in data:
                                        st.write("摘要：", data.get("summary"))
                                else:
                                    st.error("分析失敗")
                                break
                            time.sleep(1.0)
            else:
                try:
                    st.error(r.json().get("detail", r.text))
                except Exception:
                    st.error(r.text)
        except Exception as e:
            st.error(f"上傳/分析錯誤：{e}")

# ========= 分析紀錄 =========
st.subheader(" 分析紀錄")
if is_logged_in:
    try:
        r = requests.get(f"{BACKEND}{JOBS_MY_ENDPOINT}", headers=headers, timeout=30)
        if r.ok:
            jobs = r.json()
            if not jobs:
                st.caption("目前沒有分析紀錄。")
            else:
                for job in jobs:
                    cols = st.columns([3, 2, 2, 3, 3, 3])  
                    with cols[0]:
                        st.write(f"🆔 {job['job_id']}")
                    with cols[1]:
                        st.write(f"狀態: {job['status']}")
                    with cols[2]:
                        st.write(job.get("summary", "無摘要"))
                    with cols[3]:
                        st.write(f"建立時間: {job['created_at']}")
                    with cols[4]:
                        if job.get("result_filename"):
                            dr = requests.get(
                                f"{BACKEND}/results/{job['result_filename']}", 
                                headers=headers, timeout=30
                            )
                            if dr.ok:
                                st.download_button(
                                    "下載 CSV", 
                                    data=dr.content, 
                                    file_name=job['result_filename'], 
                                    key=f"dl_csv_{job['job_id']}"
                                )
                    with cols[5]:
                        if job.get("plot_filename"):
                            pr = requests.get(
                                f"{BACKEND}/results/{job['plot_filename']}", 
                                headers=headers, timeout=30
                            )
                            if pr.ok:
                                st.download_button(
                                    "下載 PNG", 
                                    data=pr.content, 
                                    file_name=job['plot_filename'], 
                                    key=f"dl_png_{job['job_id']}"
                                )
                    with cols[5]:
                        if st.button("刪除", key=f"del_{job['job_id']}"):
                            dr = requests.delete(f"{BACKEND}/jobs/{job['job_id']}", headers=headers, timeout=30)
                            if dr.ok:
                                st.success(f"已刪除 {job['job_id']}")
                                st.rerun()
                            else:
                                st.error(f"刪除失敗: {dr.text}")
        else:
            st.error(r.text)
    except Exception as e:
        st.error(f"讀取分析紀錄錯誤：{e}")
else:
    st.caption("（登入後可查看你的分析記錄列表）")


