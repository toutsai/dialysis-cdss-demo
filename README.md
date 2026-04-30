# 透析中心 CDSS 工作流原型

這個資料夾是 HD-CDSS 的下一階段骨架：以 **NocoDB + SQLite** 作為多人共用工作台，以 **Python cron 腳本** 產生月藥物調整建議，並保留未來串接院內 HIS/API 的接口。

目前先不改動既有 `HD-CDSS/v2`。這裡先建立可逐步完成的乾淨骨架，等流程穩定後再把既有規則引擎搬進來或共用。

## 設計原則

- NocoDB 負責人工維護、醫師簽核、護理執行狀態。
- Python 負責資料同步、規則引擎、Claude 摘要、通知與稽核。
- Claude 不直接做臨床判斷，只整理規則引擎結果。
- 所有需要院內資料的地方先放在 `src/adapters/hospital/`，目前都是 stub，方便未來替換成正式 API。
- 送給 Claude 的資料必須去識別化，病歷號映射只留在本地。

## 目錄

```text
dialysis-cdss/
├── docker-compose.yml
├── pyproject.toml
├── config/
│   └── thresholds.yaml
├── prompts/
│   ├── system.md
│   ├── esa_rules.md
│   ├── iron_rules.md
│   ├── mbd_rules.md
│   └── output_schema.json
├── src/
│   ├── main.py
│   ├── audit.py
│   ├── adapters/
│   │   ├── patient_source_excel.py
│   │   ├── nocodb_client.py
│   │   └── hospital/
│   │       ├── patient_client.py
│   │       ├── schedule_client.py
│   │       ├── lab_client.py
│   │       ├── medication_client.py
│   │       ├── admission_client.py
│   │       ├── procedure_client.py
│   │       ├── exam_client.py
│   │       └── notify_client.py
│   ├── domain/
│   │   ├── entities.py
│   │   ├── deidentify.py
│   │   └── rules.py
│   └── services/
│       ├── recommendation_service.py
│       ├── claude_client.py
│       └── notify.py
└── tests/
```

## 啟動 NocoDB

```powershell
cd C:\Users\suiam\Documents\New project\dialysis-cdss
docker compose up -d
```

打開 `http://localhost:8080`，建立 workspace 後依 `docs/nocodb_schema.md` 建表。

## 啟動 Streamlit 查房前台

第一版前台會讀 `exports/nocodb_seed/*.csv`，自動同步成 local SQLite：

```powershell
cd C:\Users\suiam\Documents\New project\dialysis-cdss
streamlit run app.py
```

若沒有安裝 Streamlit，請先在你的 Python 環境安裝：

```powershell
pip install -e .
```

前台流程：

```text
床位總表
  → 選擇病人
  → 主要問題 / 近期事件 / 透析醫囑 / 抽血藥物建議
```

目前 `主要問題`、`近期事件`、`透析醫囑` 可在前台編輯並存回 local SQLite。`抽血 / 藥物建議` 下一階段接 mock lab、medication 與規則引擎。

## Demo 版

若要給外院區同事測試，請使用全虛擬資料 demo 版，不要部署真實病人資料。

```powershell
cd C:\Users\suiam\Documents\New project\dialysis-cdss
$env:DIALYSIS_CDSS_DEMO="1"
$env:DIALYSIS_CDSS_DB_PATH="data\dialysis_cdss_demo.sqlite"
python -m src.demo_data
streamlit run app.py
```

Demo 預設帳號：

- `admin / admin123`
- `doctor / doctor123`
- `nurse / nurse123`
- `HN / HN123`

部署到 Streamlit Community Cloud 或 Render 的細節見 `docs/demo_deployment.md`。

若要測試新增 `現在待處理問題` 後通知固定醫師，請在 Streamlit Secrets 設定 `PROBLEM_NOTIFY_TO` 與 SMTP 帳號資訊；Gmail 請使用 app password，不要把密碼寫入 repo。

## 規則設定

前台側邊欄可切換到 `規則設定`，第一版支援調整：

- ESA：Hb 上下限、增減量百分比、暫停門檻
- 鐵劑：Ferritin/TSAT 補鐵與暫緩門檻
- CKD-MBD：P、cCa、CaXP、iPTH 門檻與含鈣降磷藥調整比例

設定檔位於：

```text
config/dose_rules.yaml
```

所有劑量建議都是草稿，必須由醫師簽核後才可執行。

## 第一個本地流程

1. 複製 `.env.example` 成 `.env`。
2. 確認 `SCHEDULE_XLSX` 指到床位表。
3. 執行：

```powershell
python -m src.main --dry-run
```

目前 `--dry-run` 只會解析床位表並跑本地資料流程，不會寫入 NocoDB 或呼叫 Claude。

## 匯出 NocoDB 種子 CSV

先用 CSV 匯入 NocoDB，最快可以檢查資料表設計是否符合查房流程。

```powershell
python scripts/export_nocodb_csv.py --schedule-xlsx "C:\Users\suiam\OneDrive\02.4 部立台北醫院\新的東西\HD-CDSS\台東榮民醫院洗腎室病人排班表 (5).xlsx"
```

輸出位置：

```text
exports/nocodb_seed/
├── patients.csv
├── dialysis_schedule.csv
├── deid_map.csv
├── problem_list.csv
├── clinical_events.csv
├── dialysis_orders.csv
├── lab_results.csv
├── medications.csv
├── recommendations.csv
├── staff.csv
└── hospital_drugs.csv
```

在 NocoDB 建好專案後，可先用這三個 CSV 匯入對應資料表：

- `patients.csv` → `patients`
- `dialysis_schedule.csv` → `dialysis_schedule`
- `deid_map.csv` → `deid_map`
- `problem_list.csv` → `problem_list`
- `clinical_events.csv` → `clinical_events`
- `dialysis_orders.csv` → `dialysis_orders`
- `lab_results.csv` → `lab_results`
- `medications.csv` → `medications`
- `recommendations.csv` → `recommendations`
- `staff.csv` → `staff`
- `hospital_drugs.csv` → `hospital_drugs`

`staff` 是人員名單；前台 `人員設定` 可新增或停用人員。停用不會刪除紀錄，會保留新增者與新增時間。
`hospital_drugs` 是本院藥物清單；前台 `本院藥物清單` 可維護 ESA、降磷藥、降鉀藥、副甲狀腺亢進藥物。

`deid_map` 只留本地，不可外傳；Claude API 只使用 `deid`。

匯入後請依 [docs/nocodb_views.md](docs/nocodb_views.md) 建立查房用 views：

- `patients`: 查房病人清單、去識別化清單
- `dialysis_schedule`: 床位總表、透析器與透析液檢查
- `problem_list`: 主要問題列表，`problem_categories` 使用 JSON array 區分 `Underlying disease` 與 `現在待處理問題`
- `clinical_events`: 近期事件
- `dialysis_orders`: 透析醫囑

## 院內串接保留點

目前以下地方都先保留 stub：

- `src/adapters/hospital/patient_client.py`
- `src/adapters/hospital/schedule_client.py`
- `src/adapters/hospital/lab_client.py`
- `src/adapters/hospital/medication_client.py`
- `src/adapters/hospital/admission_client.py`
- `src/adapters/hospital/procedure_client.py`
- `src/adapters/hospital/exam_client.py`
- `src/adapters/hospital/notify_client.py`

每個 stub 都會丟出 `NotImplementedError`，訊息中標註 `TODO(HIS)`，之後拿到院內 API 文件時可逐一替換。
