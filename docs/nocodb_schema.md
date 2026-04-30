# NocoDB Schema 草案

## patients

- `chart_no`：病歷號，本地保存，不送 Claude
- `deid`：去識別化 ID，例如 `P000001`
- `name`
- `frequency`
- `shift`
- `bed`
- `identity`
- `active`
- `source`
- `last_synced_at`

建議 NocoDB view：

- `Active patients`：`active = true`
- `By shift`：依 `frequency`, `shift`, `bed` 排序
- `Physician round list`：顯示 `name`, `chart_no`, `frequency`, `shift`, `bed`

## dialysis_schedule

- `chart_no`
- `deid`
- `name`
- `frequency`
- `shift`
- `bed`
- `dialyzer`
- `dialysate_ca`
- `source_sheet`
- `source_updated_at`

建議 NocoDB view：

- `Bed board`：依 `frequency`, `shift`, `bed` 排序
- `Dialyzer overview`：依 `dialyzer`, `dialysate_ca` 分組，方便檢查特殊透析器與透析液

## problem_list

- `chart_no`
- `deid`
- `name`
- `problem`
- `problem_categories`
- `status`
- `owner_role`
- `updated_by`
- `updated_at`
- `note`

建議 NocoDB view：

- `Active problems`：`status = Active`，依 `updated_at` 排序
- `Underlying disease`：`problem_categories` 包含 `Underlying disease`
- `待處理問題`：`problem_categories` 包含 `現在待處理問題`
- `Nurse update list`：顯示 `name`, `problem`, `problem_categories`, `status`, `owner_role`, `updated_at`, `note`

建議欄位選項：

- `status`: `Active`, `Inactive`
- `problem_categories`: JSON array，第一版選項為 `Underlying disease`, `現在待處理問題`
- `owner_role`: `醫師`, `護理長`, `護理師`

## staff

- `staff_id`
- `name`
- `role`
- `active`
- `created_by`
- `created_at`
- `inactive_at`
- `note`

用途：維護人員名單，給前台 `負責角色` 與 `更新者` 下拉選單使用。若人員調動，將 `active` 改為 `停用`，不要刪除紀錄。

## hospital_drugs

- `drug_id`
- `drug_type`
- `drug_name`
- `default_unit`
- `active`
- `created_by`
- `created_at`
- `inactive_at`
- `note`

用途：維護本院透析相關藥物清單。`drug_type` 選項為 `ESA`, `降磷藥`, `降鉀藥`, `副甲狀腺亢進藥物`。停用不刪除紀錄。

## clinical_events

- `chart_no`
- `deid`
- `name`
- `event_type`
- `event_date`
- `title`
- `event_content`
- `source`
- `updated_by`
- `updated_at`
- `note`

`TODO(HIS)`: 本院檢查、手術、住出院紀錄未來由院內 API 同步；外院紀錄先由護理師人工維護。

## dialysis_orders

- `chart_no`
- `deid`
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

`TODO(HIS)`: 若院內透析醫囑可由 HIS 或透析系統提供，改由 `hospital/medication_client.py` 或新的 dialysis-order adapter 同步。

## lab_results

- `chart_no`
- `deid`
- `name`
- `year_month`
- `item_key`
- `value`
- `unit`
- `report_date`
- `source`

`TODO(HIS)`: 目前先讀 Excel/mock；正式版改接 HIS lab API。

## medications

- `chart_no`
- `deid`
- `name`
- `year_month`
- `order_code`
- `drug_name`
- `dose`
- `frequency`
- `drug_class`
- `source`

`TODO(HIS)`: 目前先讀 Excel/mock；正式版改接 HIS medication/order API。

## recommendations

- `recommendation_id`
- `chart_no`
- `deid`
- `year_month`
- `status`
- `severity`
- `rule_id`
- `title`
- `detail`
- `evidence_json`
- `claude_summary`
- `created_at`

狀態建議：`draft` -> `pending_physician_review` -> `approved/rejected/revised` -> `pending_nursing_action` -> `done`。

## approvals

- `recommendation_id`
- `physician`
- `decision`
- `comment`
- `decided_at`

## nursing_tasks

- `recommendation_id`
- `task`
- `assignee`
- `status`
- `done_at`
- `note`

## deid_map

- `chart_no`
- `deid`
- `created_at`

這張表只留本地 NocoDB，不可送外部 API。

## api_audit_logs

- `event_id`
- `service`
- `model`
- `prompt_version`
- `payload_hash`
- `deid_payload_json`
- `response_json`
- `created_at`
- `status`
- `error`
