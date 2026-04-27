# NocoDB Views 設定指南

這份文件描述第一版查房工作台建議建立的 views。先用 NocoDB 手動設定即可，等流程穩定後再考慮自動化。

## patients

### View: 查房病人清單

顯示欄位：

- `name`
- `chart_no`
- `frequency`
- `shift`
- `bed`
- `active`

排序：

1. `frequency` ascending
2. `shift` ascending
3. `bed` ascending

篩選：

- `active` is `true`

用途：醫師或護理師進系統後的第一個入口。

### View: 去識別化清單

顯示欄位：

- `deid`
- `frequency`
- `shift`
- `bed`
- `active`

隱藏欄位：

- `name`
- `chart_no`

用途：需要截圖、討論或準備 Claude payload 時使用。

## dialysis_schedule

### View: 床位總表

顯示欄位：

- `frequency`
- `shift`
- `bed`
- `name`
- `chart_no`
- `dialyzer`
- `dialysate_ca`
- `source_updated_at`

排序：

1. `frequency` ascending
2. `shift` ascending
3. `bed` ascending

用途：每日查房、確認排班、確認人工腎臟與透析液。

### View: 透析器與透析液檢查

顯示欄位：

- `name`
- `frequency`
- `shift`
- `bed`
- `dialyzer`
- `dialysate_ca`

分組：

- `dialyzer`
- `dialysate_ca`

用途：快速檢查特殊人工腎臟或特殊 Ca 濃度病人。

## problem_list

### View: 主要問題列表

顯示欄位：

- `name`
- `problem`
- `status`
- `owner_role`
- `updated_by`
- `updated_at`
- `note`

篩選：

- `status` is `active`
- 或新版資料：`status` is `Active`

排序：

1. `updated_at` descending

用途：護理師維護、查房醫師快速掌握長期問題。

建議欄位選項：

- `status`: `Active`, `Inactive`
- `owner_role`: `醫師`, `護理長`, `護理師`

## staff

### View: 人員名單

顯示欄位：

- `staff_id`
- `name`
- `role`
- `active`
- `created_by`
- `created_at`
- `inactive_at`
- `note`

用途：人員異動時維護此表，前台會用 `active = 啟用` 的 staff 作為 `更新者` 下拉選單。離職或調動以 `停用` 處理，保留新增者與新增時間。

## hospital_drugs

### View: 本院藥物清單

顯示欄位：

- `drug_type`
- `drug_name`
- `default_unit`
- `active`
- `created_by`
- `created_at`
- `inactive_at`
- `note`

用途：維護本院常用透析藥物。類型包含 `ESA`, `降磷藥`, `降鉀藥`, `副甲狀腺亢進藥物`。

## clinical_events

### View: 近期事件

顯示欄位：

- `name`
- `event_type`
- `event_date`
- `title`
- `event_content`
- `updated_by`
- `updated_at`

排序：

1. `event_date` descending
2. `updated_at` descending

用途：查房前快速看近期檢查、手術、住出院、外院事件。

建議欄位選項：

- `event_type`: `admission`, `discharge`, `surgery`, `procedure`, `imaging`, `lab`, `outside_hospital`, `other`
- `source`: `manual`, `hospital_api`, `outside_record`

## dialysis_orders

### View: 透析醫囑

顯示欄位：

- `name`
- `order_month`
- `dialyzer`
- `dialysate_ca`
- `blood_flow`
- `dry_weight`
- `anticoagulant`
- `vascular_access`
- `updated_by`
- `updated_at`
- `note`

排序：

1. `name` ascending
2. `order_month` descending

用途：醫師確認人工腎臟、透析藥水、blood flow、dry weight、抗凝與血管通路。

## 後續表

下一階段會加入：

- `lab_results`
- `medications`
- `recommendations`
- `approvals`
- `nursing_tasks`
- `api_audit_logs`

這些表會等 HIS/mock 資料與 rule pipeline 準備好後再匯入。
