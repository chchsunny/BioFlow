import csv
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ========= 基本設定 =========
# 必要欄位
REQUIRED_COLUMNS = ["gene", "ctrl", "treat"]

# 欄位別名
COLUMN_ALIASES = {
    "gene":  ["gene", "gene_id", "symbol", "Gene", "GENE"],
    "ctrl":  ["ctrl", "control", "CTRL", "Control", "ctl"],
    "treat": ["treat", "treatment", "TREAT", "Treatment", "trt"],
}


# ========= I/O 與前處理 =========
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """把別名欄位自動改成標準欄名（不就地修改）"""
    df = df.copy()
    col_map = {}
    for std, aliases in COLUMN_ALIASES.items():
        for c in df.columns:
            if c in aliases:
                col_map[c] = std
    if col_map:
        df = df.rename(columns=col_map)
    return df


def load_data(path: str) -> pd.DataFrame:
    """讀成 DataFrame"""
    return pd.read_csv(path)


def save_result_to_csv(result_text: str, output_path: str):
    """文字型結果（Excel 開啟不亂碼）"""
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Result"])
        writer.writerow([result_text])


def save_dataframe_to_csv(df: pd.DataFrame, output_path: str):
    """表格型結果：以 utf-8-sig 儲存，方便 Excel"""
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


def validate_data(df: pd.DataFrame) -> dict:
    """
    驗證報告：
    - 是否缺欄
    - NA 分佈
    - ctrl/treat 是否可轉數值
    """
    df_norm = normalize_columns(df)
    report = {
        "row_count": int(df_norm.shape[0]),
        "na_counts": df_norm.isna().sum().to_dict(),
        "missing_columns": [],
    }

    # 必要欄位檢查（用正規化後的欄名）
    missing = [c for c in REQUIRED_COLUMNS if c not in df_norm.columns]
    report["missing_columns"] = missing

    # 嘗試將 ctrl/treat 轉數值（不改原 df，只測試可行性）
    numeric_issue = False
    for col in ("ctrl", "treat"):
        if col in df_norm.columns:
            try:
                pd.to_numeric(df_norm[col])
            except Exception:
                numeric_issue = True
    report["numeric_issue"] = numeric_issue
    return report


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    基本清理：
    - 欄位別名正規化
    - 只保留必要欄位
    - 轉為數值，移除無法轉換或缺值
    - gene 去重複
    """
    df = normalize_columns(df)

    cols = [c for c in REQUIRED_COLUMNS if c in df.columns]
    if cols:
        df = df[cols].copy()

    # 轉數值；無法轉換→NaN
    for col in ("ctrl", "treat"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 去掉全空、必要欄位缺值
    df = df.dropna(how="all")
    df = df.dropna(subset=[c for c in REQUIRED_COLUMNS if c in df.columns])

    # gene 去重
    if "gene" in df.columns:
        df = df.drop_duplicates(subset=["gene"])

    return df


# ========= 分析與視覺化 =========
def compute_diff(df: pd.DataFrame, eps: float = 1e-9):
    """
    計算 ctrl vs treat 的差異：
    - delta = treat - ctrl
    - fold_change = (treat + eps) / (ctrl + eps)
    - log2FC = log2(fold_change)
    - direction 依 |log2FC| 門檻分類（預設 1 => 倍數>=2 算顯著變動）
    回傳：result_df（含上述新欄位）、summary（文字摘要）
    """
    df = df.copy()
    # 必要欄位檢查（保險）
    for c in ("ctrl", "treat"):
        if c not in df.columns:
            raise ValueError(f"compute_diff 需要欄位 '{c}'")

    df["delta"] = df["treat"] - df["ctrl"]
    df["fold_change"] = (df["treat"] + eps) / (df["ctrl"] + eps)
    df["log2FC"] = np.log2(df["fold_change"])

    # 方向標記
    thr = 1.0
    df["direction"] = "unchanged"
    df.loc[df["log2FC"] >= thr, "direction"] = "up"
    df.loc[df["log2FC"] <= -thr, "direction"] = "down"

    # 排序：變動幅度大者在前
    df = df.sort_values(by="log2FC", key=lambda s: np.abs(s), ascending=False)

    up = int((df["direction"] == "up").sum())
    down = int((df["direction"] == "down").sum())
    total = int(df.shape[0])
    summary = f"共 {total} 基因；|log2FC|>=1 上調 {up}、下調 {down}"

    return df, summary


def plot_volcano(df: pd.DataFrame, output_path: str, fc_threshold: float = 1.0):
    """
    繪製火山圖（純 matplotlib）：
    - X 軸：log2FC
    - Y 軸：|delta|（暫以 |treat-ctrl| 取代 p-value）
    - 顏色依 direction（up/down/unchanged）
    """
    data = df.copy()

    if "log2FC" not in data.columns:
        raise ValueError("plot_volcano 需要欄位 'log2FC'")
    if "delta" not in data.columns and "abs_delta" not in data.columns:
        raise ValueError("plot_volcano 需要欄位 'delta' 或 'abs_delta'")

    if "abs_delta" not in data.columns:
        data["abs_delta"] = data["delta"].abs()

    # 顏色對應
    color_map = {"up": "red", "down": "blue", "unchanged": "grey"}
    colors = data["direction"].map(color_map).fillna("grey")

    plt.figure(figsize=(8, 6))
    # 散點（一次畫完）
    plt.scatter(
        data["log2FC"].values,
        data["abs_delta"].values,
        c=colors.values,
        s=20,
        alpha=0.8,
        linewidths=0,
    )

    # 簡單圖例
    import matplotlib.patches as mpatches
    handles = [
        mpatches.Patch(color="red", label="up"),
        mpatches.Patch(color="blue", label="down"),
        mpatches.Patch(color="grey", label="unchanged"),
    ]
    plt.legend(handles=handles, loc="best", frameon=False)

    # 臨界線
    plt.axvline(x=fc_threshold, color="black", linestyle="--", linewidth=1)
    plt.axvline(x=-fc_threshold, color="black", linestyle="--", linewidth=1)

    plt.xlabel("log2 Fold Change (log2FC)")
    plt.ylabel("|Delta| (proxy for significance)")
    plt.title("Volcano Plot")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
