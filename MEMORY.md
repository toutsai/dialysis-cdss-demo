# 2026-04-27 專案交接紀錄

這份文件用來讓下一次對話快速接上目前狀態。若明天重新開啟 Codex，可以先請 Codex 讀取：

```text
D:\GitHub-Projects\dialysis-cdss\docs\session_handoff_2026-04-27.md
```

## 專案位置與 GitHub

- 本機專案位置：`D:\GitHub-Projects\dialysis-cdss`
- GitHub repo：`https://github.com/toutsai/dialysis-cdss-demo.git`
- 主要分支：`main`
- 目前已 push 到 GitHub，Streamlit Cloud 會從 `main` 自動部署。
- 最新重要 commit：
  - `745ea64 Strengthen patient tab styling`
  - `caf5c33 Use keyed container for reminders`
  - `3159459 Fix handoff reminder navigation`
  - `91de762 Initial dialysis CDSS demo app`

## 目前架構

目前已經從早期的 NocoDB 後台方向，逐步改成：

```text
Streamlit 前台
↓
SQLite 本機或 demo 資料庫
↓
GitHub / Streamlit Community Cloud 測試部署
```

NocoDB 目前不是必要元件。Docker Desktop 只有在要跑 NocoDB、PostgreSQL、容器化測試或院內主機 Docker Compose 時才需要開。日常本機開發可以直接跑 Streamlit。

## 本機啟動

```powershell
cd "D:\GitHub-Projects\dialysis-cdss"
streamlit run app.py
```

本機常用網址：

```text
http://localhost:8502
```

如果 8502 沒有啟動，可用：

```powershell
streamlit run app.py --server.port 8502
```

## Streamlit Cloud Demo

部署設定：

- Repository：`toutsai/dialysis-cdss-demo`
- Branch：`main`
- Main file path：`app.py`
- Secrets：

```toml
DIALYSIS_CDSS_DEMO = "1"
DIALYSIS_CDSS_DB_PATH = "data/dialysis_cdss_demo.sqlite"
```

Demo 模式會自動產生假資料，不使用真實病人資料。

Demo 帳號：

```text
admin / admin123
doctor / doctor123
nurse / nurse123
HN / HN123
```

## 今天完成的重點

### 1. 專案搬移與 GitHub

- 專案已從 `C:\Users\suiam\Documents\New project\dialysis-cdss` 搬到 `D:\GitHub-Projects\dialysis-cdss`。
- 已建立 Git remote：

```text
origin https://github.com/toutsai/dialysis-cdss-demo.git
```

- 已 push 到 GitHub。

### 2. Demo 部署準備

- 已整理 demo 部署方式。
- `src/demo_data.py` 可產生假資料。
- `.gitignore` 已排除 SQLite、本機資料、NocoDB data、匯出檔、快取與 secrets。

### 3. 今日提醒修正

原本點今日提醒卡會登出，原因是使用 HTML link 改 query params，Streamlit Cloud 會重開 session，導致 `st.session_state` 的登入狀態消失。

已改成：

- 今日提醒使用 Streamlit 原生 button。
- 點擊後只更新 session state：
  - `selected_chart_no`
  - `patient_tab = 醫護交班`
  - `patient_tab_target = 醫護交班`
  - `handoff_focus_row_id`
- 不再透過 URL 重新載入頁面。

### 4. 今日提醒顯示格式

目前提醒卡文字規則：

```text
床號 姓名｜交班內容
```

不再顯示：

- 一般/重要
- 日期

原因：今日提醒已經代表目標日期為今天，不需要重複顯示日期。

### 5. 今日提醒顏色與間距

使用者希望今日提醒卡更顯眼，偏橘色或粉紅色。

目前做法：

- 使用 `st.container(key="handoff-reminders")`
- CSS 鎖定 `.st-key-handoff-reminders`
- 嘗試將提醒按鈕改為橘色系：
  - 背景 `#fff7ed`
  - 邊框 `#fb923c`
  - 左側橘色強調線 `#ea580c`

注意：Streamlit Cloud 上 CSS 是否完全套用仍需實測。若仍顯示藍色，下一步可改成「橘色 HTML 卡片 + 原生小按鈕」或改用 custom component，避免被 Streamlit button 預設樣式覆蓋。

### 6. 病人頁籤字體

使用者希望工作台右側病人姓名下方 5 個頁籤字體更大、更粗：

- 主要問題
- 近期事件
- 醫護交班
- 透析醫囑
- 抽血 / 藥物建議

目前做法：

- 將 segmented control 包入 `st.container(key="patient-tabs")`
- CSS 鎖定 `.st-key-patient-tabs`
- 設定：
  - `font-size: 1.1rem`
  - `font-weight: 850`
  - `min-height: 2.45rem`

注意：使用者回報前一版沒有變化，這一版已改用固定 key container，但仍需在 Streamlit Cloud 上實測。

## 目前產品設計方向

### 查房工作台

左側：

- 床位總表與人數
- 動態頻率選項
- 動態班別選項
- 搜尋姓名/病歷號/床號
- 今日提醒
- 依床號排序的病人列表

右側：

- 病人姓名 / 病歷號
- DW、AK、藥水 Ca、頻率、班別、床位
- 頁籤：
  - 主要問題
  - 近期事件
  - 醫護交班
  - 透析醫囑
  - 抽血 / 藥物建議

### 權限概念

目前已建立登入角色：

- 醫師
- 護理師
- 護理長

權限方向：

- 人員設定：醫師/護理長可編輯，護理師只看。
- 本院藥物清單：醫師可編輯，護理師只看。
- 規則設定：醫師可編輯，護理師只看。
- 主要問題、近期事件、醫護交班：醫師/護理長/護理師可編輯。
- 透析醫囑：醫師可編輯。

## 下一步工作建議

使用者已明確表示，接下來要做：

```text
調整用藥規則
抽血 / 藥物調整頁面整修
```

建議下一次從以下順序開始。

### 1. 先整理抽血 / 藥物建議頁面

目標：

- 讓頁面更像臨床醫師看得懂的月藥物調整工作區。
- 不要只是表格堆疊。

可改成：

```text
上方：分析月份 + 病人摘要
中間左：本月抽血重點
中間右：目前藥物
下方：規則引擎建議 + 劑量調整草稿
```

建議優先顯示：

- Hb
- Ferritin
- TSAT
- Ca
- P
- cCa
- CaXP
- iPTH
- ESA 目前劑量
- 鐵劑
- 降磷藥
- 降鉀藥
- 副甲狀腺亢進藥物

### 2. 再調整用藥規則

規則應先維持 deterministic rule engine，不直接讓 AI 做臨床判斷。

建議規則分組：

- ESA / Hb
- Iron / Ferritin / TSAT
- CKD-MBD / Ca / P / iPTH
- Potassium / 降鉀藥

規則設定頁可以逐步從 JSON/表格改成表單式：

```text
ESA
- Hb 下限
- Hb 上限
- Hb 過高暫停值
- 增量百分比
- 減量百分比
- 鐵狀態不足時是否禁止 ESA 增量

Iron
- Ferritin 低值
- TSAT 低值
- Ferritin 過高停用值
- TSAT 過高停用值

MBD
- P 高值
- Ca 高值
- iPTH 高值
- CaXP 高值
```

### 3. 再思考 Claude API 角色

目前比較安全的模式：

```text
抽血/藥物資料
↓
規則引擎產生 deterministic 建議
↓
Claude 只負責整理文字與摘要
↓
醫師簽核
```

不要讓 Claude 直接決定藥物劑量。

## 注意事項

- 不要把真實 SQLite DB、病人 CSV、匯出檔 push 到 GitHub。
- Demo repo 只能放假資料。
- Streamlit Cloud 上 SQLite 適合 demo，不適合正式多人共用資料庫。
- 正式院內版本建議放院內主機，資料庫用 SQLite 或 PostgreSQL，視多人寫入需求決定。
- Docker Desktop 目前非必要，除非要回頭跑 NocoDB 或容器化服務。

## 下一次開場建議

可直接對 Codex 說：

```text
請先讀取 D:\GitHub-Projects\dialysis-cdss\docs\session_handoff_2026-04-27.md
接著幫我整修「抽血 / 藥物建議」頁面，並開始調整用藥規則設定。
```

