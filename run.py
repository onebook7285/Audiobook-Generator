import os
import sys

# 將專案根目錄添加到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 導入應用並運行
import uvicorn

if __name__ == "__main__":
    print(f"啟動服務器... (工作目錄: {os.getcwd()})")
    print(f"Python 路徑: {sys.path}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
