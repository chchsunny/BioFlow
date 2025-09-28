from app.utils import compute_diff

def run_analysis(df):
    """
    接收一份清理好的 DataFrame（要有 gene/ctrl/treat 三個欄位），
    把它丟給 compute_diff 做數學運算，
    然後回傳兩個結果：
      1. summary (文字摘要，用來顯示)
      2. result_df (分析表，通常會存成 CSV)
    """
    result_df, summary = compute_diff(df)
    return summary, result_df
