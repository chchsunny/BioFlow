#  BioFlow 

BioFlow 是一套專為生醫領域設計的資料處理與分析平台，支援命令列操作 (CLI)、FastAPI 後端 API 與 Streamlit Web UI，並提供 Docker Compose 一鍵部署。使用者可透過 CSV 檔上傳實驗數據，系統會自動進行資料清理、差異分析並產生結果檔案（CSV、PNG 火山圖），BioFlow 可廣泛應用於 RNA-seq 等實驗數據分析與結果視覺化。

---

##  features

-  支援 CLI 命令列操作（CSV 檔案讀取與驗證）
-  提供 FastAPI API（Swagger /docs 測試介面）
-  提供使用者 註冊 / 登入功能
-  支援 Web UI (Streamlit 分析面板)
-  支援 Docker Compose 一鍵部署
-  支援 CSV 上傳 → 自動分析 → 下載結果 (CSV/PNG 火山圖)

---

##  start up

1. 終端機執行
```bash
git clone https://github.com/chchsunny/BioFlow.git
```
2. 開啟docker左下角呈現Engine running
3. 終端機執行
```bash
cd BioFlow
```
```bash
docker compose up --build
```
4. 啟動後
- API (FastAPI)：http://localhost:8000/docs
- 前端 (Streamlit)：http://localhost:8501

---

##  New Browser Frontend (HTML/CSS/JS)

我們新增了 `frontend/` 靜態網站，提供與 Streamlit 類似的介面：登入/註冊、CSV 上傳分析、任務列表、結果下載/刪除。

本機開發步驟：

1) 啟動 API：
```bash
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000
```

2) 啟動靜態網站（任一靜態伺服器皆可）：
```bash
python -m http.server 5500 -d frontend
```

3) 瀏覽器開啟 http://localhost:5500

如需調整 API 位址，修改 `frontend/app.js` 內的 `API_BASE`。

---

##  results
<img width="1566" height="772" alt="image" src="https://github.com/user-attachments/assets/2fe687d1-8f01-46f3-8316-54ae749ba100" />

---

##  MIT License
本專案使用 MIT License 授權，歡迎自由使用與參考

