# Demo 版部署說明

這份文件是給「外院區同事測試介面」用。Demo 版只使用虛擬資料，不應連接任何真實病人資料、院內 HIS/API 或正式資料庫。

## Demo 模式做了什麼

- 自動產生 `data/dialysis_cdss_demo.sqlite`
- 病人全部是 `測試病人01`、`測試病人02` 這類假名
- 病歷號全部是 `D00001` 這類 demo 編號
- 交班、近期事件、抽血、藥物、醫囑都是虛擬資料
- 預設登入帳號：
  - `admin / admin123`
  - `doctor / doctor123`
  - `nurse / nurse123`
  - `HN / HN123`

## 本機產生 Demo DB

```powershell
cd "C:\Users\suiam\Documents\New project\dialysis-cdss"
$env:PYTHONPATH="C:\Users\suiam\Documents\New project\dialysis-cdss"
python -m src.demo_data
```

啟動 demo 版：

```powershell
$env:DIALYSIS_CDSS_DEMO="1"
$env:DIALYSIS_CDSS_DB_PATH="C:\Users\suiam\Documents\New project\dialysis-cdss\data\dialysis_cdss_demo.sqlite"
streamlit run app.py
```

## Streamlit Community Cloud 部署

1. 確認 GitHub repo 內有：
   - `app.py`
   - `requirements.txt`
   - `src/demo_data.py`
   - `src/db.py`
2. 不要上傳任何真實 `.sqlite` 或 `.db` 檔案。
3. 到 Streamlit Community Cloud 建立 app。
4. Entry point 選 `app.py`。
5. Advanced settings / Secrets 加入：

```toml
DIALYSIS_CDSS_DEMO = "1"
DIALYSIS_CDSS_DB_PATH = "data/dialysis_cdss_demo.sqlite"
```

第一次啟動時，app 會自動產生 demo SQLite。

## Render 部署概念

Render 或其他雲端主機也可以用同樣概念：

- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Environment variables:
  - `DIALYSIS_CDSS_DEMO=1`
  - `DIALYSIS_CDSS_DB_PATH=data/dialysis_cdss_demo.sqlite`

## 安全提醒

- Demo 網址可以給同事測操作流程，但裡面只能放假資料。
- 不要把 `data/dialysis_cdss.sqlite`、`nocodb-data/noco.db` 或任何真實匯出 CSV 推到 GitHub。
- 真實資料版本應部署在院內主機、VPN 或資訊室核准環境。
- Demo 版 SQLite 若部署在免費雲端，資料可能在服務重啟後還原或消失；它適合測 UI，不適合收正式回饋資料。
