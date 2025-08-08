# BioFlow 生物資料處理與視覺化平台
BioFlow 是一套專為生醫領域設計的資料處理工具，支援命令列操作（CLI），可自動處理 RNA-seq 等實驗資料、進行分析並輸出報告，未來將擴展為具備 API 與 Web UI 的全流程平台。

BioFlow is a bioinformatics data processing and visualization platform. It starts as a CLI-based tool for analyzing RNA-seq data and will evolve into a full-featured system with API and web UI support.

---

## 🔧 功能 Features

- ✅ 支援 CLI 命令列操作（CSV 檔案讀取與驗證）
- ✅ 自動判斷資料筆數並產出分析結果
- ✅ 分析結果輸出為 CSV（`output.csv`）
- 🛠️ 未來將擴充 FastAPI / Flask 支援檔案上傳
- 🛠️ 將整合差異分析與統計視覺化功能（Seaborn / Plotly）

---

## 🚀 快速開始 Quick Start

### 安裝 Python 套件
```bash
pip install -r requirements.txt  # （未來會補上）


````markdown
### 執行 CLI 工具

```bash
python main.py --file data/sample.csv --out result.csv

## License

This project is licensed under the MIT License.

### 🖥️ CLI 執行畫面 (Console Output)

```bash
$ python main.py --file data/sample.csv --out result.csv
分析完成結果：共 4 筆資料
你輸入的檔案路徑是：data/sample.csv
分析結果已儲存到:result.csv

