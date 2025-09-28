import argparse
import pandas as pd 
from app.analysis import run_analysis
from app.utils import load_data, save_result_to_csv

def main():
    parser = argparse.ArgumentParser(description="資料分析 CLI 工具")
    parser.add_argument("--file", required=True, help="輸入 CSV 檔案路徑")
    parser.add_argument('--out' , default='result.csv' , help='分析結果輸出成csv檔案路徑')
    args = parser.parse_args()

    try:
        data = load_data(args.file)

        if data is None or data.empty or len(data) <= 1:
            print("警告:資料為空或僅有標題，無有效資料可分析。")
            return
        
        result = run_analysis(data)
        print("分析完成結果：", result)
        print(f"你輸入的檔案路徑是：{args.file}")

        save_result_to_csv(result, args.out)
        print(f"分析結果已儲存到:{args.out}")

    except FileNotFoundError:
        print(f"錯誤:找不到檔案{args.file}")
    except Exception as e:
        print(f"發生錯誤:{e}")
        
if __name__ == "__main__":
    main()
