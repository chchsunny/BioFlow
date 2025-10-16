#  BioFlow

BioFlow 是一套專為生醫領域設計的資料處理與分析平台。前端採用 HTML/CSS/JavaScript，後端使用 FastAPI + SQLite，並提供 Docker Compose 一鍵部署。使用者可透過瀏覽器登入、上傳 CSV，系統自動進行資料驗證/清理與差異分析，輸出結果 CSV 與火山圖（PNG）。

---

##  Features

-  使用者登入/註冊（JWT）與個別管理
-  CSV 上傳 → 自動分析 → 下載結果（CSV / PNG 火山圖）
-  差異分析流程內建資料驗證與清理
-  前端：原生 HTML/CSS/JS
-  後端：FastAPI + SQLite
-  Docker Compose 一鍵啟動

---

##  Quick Start（Docker）

1) 啟動 Docker Desktop（確保 Engine running）

2) 在專案根目錄執行：
```bash
docker compose up -d --build
```

3) 開啟：
- Web 前端：`http://localhost:8000/web/`
- API 文件：`http://localhost:8000/docs`



---

##  Results
<img width="1566" height="772" alt="image" src="https://github.com/user-attachments/assets/2fe687d1-8f01-46f3-8316-54ae749ba100" />


---

##  License
本專案使用 MIT License 授權，歡迎自由使用與參考。

