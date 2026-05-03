# 醫院 HIS / LIS 串接骨架

本系統把醫院資料來源視為外部 adapter。第一階段先同步抽血資料到本地 `lab_results`；藥物資料因院內醫囑與實際給藥邏輯較複雜，先由 CDSS 前台人工維護。這樣之後醫院若從 CSV/SFTP 改成 REST API 或 FHIR，只需要替換 `src/adapters/hospital/`。

## 第一版資料流

```text
醫院 LIS / HIS 抽血資料
  ↓ CSV / SFTP / REST / FHIR
src/adapters/hospital/*
  ↓ normalized rows
src/services/hospital_sync.py
  ↓ replace source-matched synced rows
SQLite: lab_results
  ↓
Streamlit 前台與規則引擎
```

藥物資料第一階段不走同步流程，主要由前台輸入；`medications` 仍是規則引擎讀取的本地資料表。

## 已建立的程式入口

- `src/adapters/hospital/lab_client.py`
  - 目前支援 CSV bridge：`HOSPITAL_LAB_CSV` 或 `--lab-csv`
  - 未來醫院給 API 後，在這裡把醫院 JSON/FHIR 轉成標準欄位
- `src/adapters/hospital/medication_client.py`
  - 目前保留為選配 adapter
  - 預設不執行，除非 CLI 明確帶入 `--medication-csv` 或 `--include-medications`
  - 第一階段藥物建議由前台人工輸入的 `medications` 資料產生
- `src/services/hospital_sync.py`
  - 統一同步流程
  - 補上本地病人姓名 / deid
  - 寫入 SQLite
  - 寫 audit log
- `scripts/sync_hospital_data.py`
  - 可手動執行同步，之後可交給 Windows 工作排程或院內 cron

## CSV bridge 格式

若醫院第一階段無法提供 API，可以先請資訊室每日匯出 CSV 到院內安全資料夾。

### 抽血 CSV 建議欄位

最低需求：

- `chart_no`
- `item_key` 或 `item_code` / `lab_code`
- `value`
- `unit`
- `report_date`

可選：

- `deid`
- `name`
- `year_month`
- `source_record_id`

系統會嘗試把常見項目名稱轉成規則引擎使用的 key，例如 `HGB` -> `Hb`、`PHOS` -> `P`、`PTH` -> `iPTH`。

### 藥物 CSV 建議欄位（保留，第一階段不啟用）

最低需求：

- `chart_no`
- `drug_name`
- `dose`
- `frequency`
- `order_date` 或 `start_date`

可選：

- `deid`
- `name`
- `year_month`
- `order_code`
- `drug_class`
- `source_record_id`
- `end_date`
- `status`

若未來要啟用藥物同步，沒有 `drug_class` 時，系統會先用藥名做粗略分類，例如 ESA、IRON_IV、CALCIUM_BINDER、NON_CALCIUM_BINDER、K_BINDER、PTH、OTHER。

## 手動測試同步

```powershell
cd D:\GitHub-Projects\dialysis-cdss
python scripts\sync_hospital_data.py `
  --lab-csv "D:\secure-export\labs.csv" `
  --start-date 2026-04-01 `
  --end-date 2026-04-30
```

若未來真的要測藥物同步，再明確加入：

```powershell
python scripts\sync_hospital_data.py `
  --lab-csv "D:\secure-export\labs.csv" `
  --medication-csv "D:\secure-export\medications.csv" `
  --include-medications
```

若要只同步特定病人：

```powershell
python scripts\sync_hospital_data.py --lab-csv "D:\secure-export\labs.csv" --chart-no 123456A
```

## 跟醫院資訊室要的資料

請優先確認以下項目：

- 是否有 FHIR API、院內 REST API，或只能先 CSV/SFTP。
- 抽血資料欄位：病歷號、檢驗代碼、檢驗名稱、數值、單位、採檢日、報告日、報告狀態。
- 藥物資料第一階段不強求串接；若未來要串，才需要確認病歷號、醫令碼、藥品碼、藥名、劑量、頻率、途徑、開始日、結束日、狀態、實際給藥/施打紀錄。
- 查詢方式：單一病人、病人清單、日期區間、是否支援批次查詢。
- 認證方式：院內 IP 白名單、VPN、API key、OAuth2、client certificate。
- 測試環境：sandbox URL、測試病歷號、假資料。
- 稽核需求：誰查詢、查詢時間、查詢目的、失敗紀錄保存方式。

## 安全原則

- 第一版只讀資料，不回寫 HIS。
- API token / 密碼不可寫入 repo。
- 同步程式寫入 audit log，但不保存完整原始 API payload。
- 外部 AI 不直接接觸可識別病人資料；去識別化仍在本地完成。
