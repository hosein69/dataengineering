# TEST_AND_INVARIANTS — Phase 0

## 1. کار انجام‌شده و حدود اعتبار

- ZIP اصلی دست‌نخورده؛ اعضای استخراج‌شده با bytes archive مقایسه شدند: **0 changed original files**.
- همه 268 Python file با AST parse شدند: **0 syntax errors**. این import/runtime correctness نیست.
- `python run_all_tests.py` در root پکیج با `GSI_DWH_PATH` آزمایشی و `PYTHONDONTWRITEBYTECODE=1` اجرا شد؛ خروجی کامل در evidence/full_test_run.log است.
- خروجی خود runner: **832 تست/بررسی موفق، 41 ناموفق**. بررسی لاگ نشان داد **هر 41 مجموعه به دلیل No module named pytest اجرا نشده‌اند**؛ این‌ها functional failure کد محسوب نمی‌شوند. تعداد 832 مجموع گزارش‌شده runner است، نه تعداد pytest items.
- نصب pytest در مسیر جداگانه امتحان شد؛ package در محیط قابل دریافت نبود. هیچ dependency پروژه تغییر نکرد. تست‌های نیازمند pytest همچنان **BLOCKED / NOT EXECUTED** هستند.
- 11 سناریوی synthetic بازتولید + یک negative control مستقل از pytest اجرا شد. فایل‌های probe خارج درخت source هستند. نتایج، ایراد واقعی روی ورودی مشخص را نشان می‌دهند؛ نرخ وقوع آن‌ها در production **UNKNOWN / NEEDS EVIDENCE** است.
- تست مرورگری Streamlit، Outlook COM، شبکه سازمانی، data reconciliation 17 source و production database migration اجرا نشده‌اند. historical log داخل ZIP نتیجه این اجرا نیست.

## 2. بازتولیدهای مستقل

| Probe | Findings | Input | Actual observed result | Verdict |
|---|---|---|---|---|
| P01 | F001/F002 | Publish R1؛ mutate/build R2 + BLOCK؛ read chatbot/Cashflow | pointer=R1؛ chatbot NEW_BLOCKED با R1؛ source frames قبلی ناقص | FAIL — defect reproduced |
| P02 | F004 | دو order با material مشترک | 1 case و ORDER_COUNT=2 | FAIL |
| P03 | F005 | دو Abbasi native rows با محتوای یکسان | generic observations=1 از 2 | FAIL |
| P04 | F007/F008 | 100 USD و 100 EUR؛ status تایید نشده | 200 EUR و هر دو ALLOCATED | FAIL |
| P05 | F009 | دو ردیف همان COMMIT_ROW، هر کدام balance=50 | balance=100 | FAIL conditional on repeated source ID |
| P06 | F017 | header PR/material متفاوت از po.PR/material | PO fact generic keys هدر را نگه داشت | FAIL conditional on source conflict |
| P07 | F020 | join دو کلید مرکب کاملاً blank | match و R=99 | FAIL |
| P08 | F023 | دو نسخه فایل، هر کدام balance=50 | totals_by_currency=100 | FAIL |
| P09 | F024 | KB source folder موقتاً unavailable و سپس restored | deleted=1؛ active after restore=0 | FAIL |
| P10 | F025 | duplicate PR و blank item | GRAIN_UNIQUENESS passed=True | FAIL |
| P11 | F027 | دو REG مستقل، هر کدام COMMIT_ROWS=1 | CONFLICTING_SOURCE_EVENT_ID | FAIL |
| N01 | none | find_col po.Purchasing Document روی فقط po.Purchasing Doc. Type | None؛ فرض mismatch مشخص تأیید نشد | NEGATIVE CONTROL |

جزئیات ورودی/خروجی در `evidence/probes.py`, `more_probes.py`, `final_probes.py` و JSON متناظر؛ این فایل‌ها patch پروژه نیستند. P01 خود gate pointer را سالم نگه داشت، اما dataset reader isolation شکست خورد؛ این تمایز برای طراحی regression ضروری است.

## 3. Invariants الزامی برای مرحله اصلاح

این جدول **spec پیشنهادی acceptance** است؛ همه موارد در تست‌های موجود پیاده نشده‌اند.

| ID | Invariant | Counterexample / fixture | Gate / consumer | Current evidence |
|---|---|---|---|---|
| I01 | blocked/failed run تمام published reads قبلی را byte/semantic stable نگه دارد | R1 success→R2 changed/unchanged records→blocked | report, chatbot, cashflow, files | F001/F002/F012 fail |
| I02 | هر observation به file/sheet/physical-row و run membership قابل ردیابی باشد | duplicate content at 2 rows؛ replay unchanged file | Raw/native/DWH | F005/F006 gap |
| I03 | omission در export بدون full-snapshot contract deletion نیست | missing row + optional source outage | all source facts | F003/F010 |
| I04 | case identity از shared dimensions ساخته نشود | 2 orders same material/employee | process cases/matrix | P02 fail |
| I05 | native relation != derived relation و هر relation row references داشته باشد | REG_FILE N:M hub + first_valid projection | DWH, chatbot | F006 |
| I06 | مجموع monetary amounts فقط در grain/CCY/UOM یکسان | mixed currencies per REG/order | NTSW, commercial, FX | P04 fail |
| I07 | repeated obligation ID مقدار را زیاد نکند؛ independent equal-valued IDs حفظ شوند | duplicate COMMIT_ROW vs 2 IDs | commitment | P05 fail |
| I08 | negative/revoked status allocation مثبت نشود | تایید نشده؛ لغو بعد از allocation date | NTSW request state | P04 fail |
| I09 | keyless/invalid rows حفظ و quarantine شوند و sums را آلوده نکنند | orphan FX، malformed amount، no REG with valid ORDER | financial evidence | adapter partial protection؛ F026 gap |
| I10 | blank composite keys هیچ match نسازند | ('',''), ('O','') + null/NaN + delimiter collision | safe_merge | P07 fail |
| I11 | many-to-one projection explicitly declared باشد؛ native RHS rows قابل رجوع | multiple LC/BL declaration rows | flat joins vs native facts | F019 |
| I12 | PR/PO/item/material semantic conflicts قرنطینه شوند | header PR != po.PR | SAP facts/relations | P06 fail |
| I13 | deletion flags و current selection explicit باشد | PR deleted + PO active و عکس | SAP/current views | F003/F017 |
| I14 | reorder source rows event تازه نسازد | same workflow reordered | workflow/current status | F018 |
| I15 | latest PR status از item lexical order گرفته نشود | items 2/10/20 با dates متفاوت | chatbot | F018 |
| I16 | stock sum نیازمند bucket identity؛ max policy field lineage داشته باشد | 2 equal buckets vs duplicate snapshots؛ 2 sheets differing dates | Oracle supply | F013/F014 |
| I17 | missing money != 0، missing date != today | absent NTSW/FX/date | legacy and cashflow parity | F031 |
| I18 | دریافت سند != رسید مالی؛ SWIFT != receipt | only DOC_RECEIVED / only SWIFT | process terminal/payment | F022/F039 |
| I19 | source field producer/consumer mappings reachable باشند | only BL_DISCHARGE_DATE and SATA_TRACKING_DATE populated | derive/eventlog/location | F021 |
| I20 | valid source_event_id globally scoped به source business entity باشد | 2 REG with COMMIT_ROWS=1 | cashflow replay | P11 fail |
| I21 | snapshot totals فقط published selected files، نه همه نسخه‌ها | same amount in 2 file hashes | fx_obligation | P08 fail |
| I22 | optional branch failure unrelated domain evidence را نابود نکند | NTSW commitment invalid with licence/allocation valid | adapter/gates | F011 |
| I23 | required frame absent و schema unmapped خروجی سالم شمرده نشود | optional source return {}; empty sheet | source contracts | F010/F025 |
| I24 | nullable key uniqueness مستقل از missing component باشد | duplicate PR+blank item | quality gate | P10 fail |
| I25 | stale fallback provenance/age به snapshot اصلی اشاره کند | 2 consecutive fallback runs | source frames/cashflow | F033 |
| I26 | KB root outage deletion نیست و restored unchanged file فعال شود | rename source folder temporarily | index/search/static | P09 fail |
| I27 | retrieval error با no evidence متفاوت باشد | SQLite failure/unsupported alphanumeric ID | chatbot | F034 |
| I28 | پاسخ بر اساس citation مرتبط و effective authority باشد؛ uncertainty حفظ شود | contradictory/outdated docs, weak token overlap | KB/AnythingLLM | F035 |
| I29 | export clearance در import KPI وارد نشود | ExportClearance matching *Clearance* | import report/process | F029 conditional |
| I30 | official artifacts فقط پس از gate promote شوند | invalid source contract but build_report=true | files/publish | F012 |
| I31 | current pointers monotonic و migration repeatable باشد | interleaved completion/publish; old schema version=1 | warehouse lifecycle | F040 static risk |
| I32 | configuration reload authority/merge order همه consumers را یکسان تغییر دهد | changed YAML then reload | canonical/cashflow/population | F032 |

## 4. کنترل‌های موجود و شکاف پوشش

| Existing mechanism | Proven scope | What it does not prove |
|---|---|---|
| Raw reconciliation / FK / integrity | physical rows و DB structure | business semantic correctness |
| safe_merge row count | تعداد سطر left تغییر نکند | حفظ multiple RHS facts / monetary totals |
| Source GrainContract | named frame keys/columns | contracts absent frames؛ many sources INFO-only |
| PROCESS_ROW_PRESERVATION | frame input count vs generic observations | physical native row preservation after adapter aggregation |
| final partition count | main+excluded+to_resolve=df | buckets semantically correct or deduped amounts |
| wh.publish quality checks | pointers only after completed/passing run | mutable DWH/table/file isolation |
| SAP tests | selected semantic frames and chatbot happy paths | blocked R2 mutation leak، conflicting po.PR، reordered history |
| Cash Flow Decimal | exact operations after parsing | correctness/identity of upstream float/source facts |
| KB self-index guard | output/source topology | inaccessible root vs true deletion |

## 5. اجراهای runner به تفکیک مجموعه

نام بعضی suiteها از label فارسی legacy آمده است؛ inventory بخش بعد exact file name را ثبت می‌کند.

| Suite label | Status |
|---|---|
| test_anythingllm_learning_v29 | BLOCKED: pytest unavailable |
| ۴) معماری، اختلاف نسخه و لاگ رویداد | EXECUTED — runner output attached |
| test_cashflow_dwh_v29_7_2 | BLOCKED: pytest unavailable |
| test_cashflow_hardening_v29_7_1 | BLOCKED: pytest unavailable |
| test_cashflow_v29_7 | BLOCKED: pytest unavailable |
| test_cluster_scope_v284 | BLOCKED: pytest unavailable |
| ۵) قرارداد گزارش (باگ موجودی/مقاومت) | EXECUTED — runner output attached |
| ۲۷) مرکز مخاطبان و منابع | EXECUTED — runner output attached |
| ۳) مقاومت قطعه و بحرانی بودن | EXECUTED — runner output attached |
| ۶) منطق داشبورد و خروجی‌ها | EXECUTED — runner output attached |
| test_dashboard_criticality_repair_v28 | BLOCKED: pytest unavailable |
| ۲۲) سیستم طراحی — توکن، کامپوننت، دسترس‌پذیری | EXECUTED — runner output attached |
| ۸) ادعاهای مستندات | EXECUTED — runner output attached |
| ۹) بسته ایمیل مدیریتی | EXECUTED — runner output attached |
| test_fullstack_v29_6_10 | BLOCKED: pytest unavailable |
| test_fx_adapter_quarantine_v28 | BLOCKED: pytest unavailable |
| test_fx_obligation_v28_1 | EXECUTED — runner output attached |
| ۱۷) FX Traceability V26.16 | EXECUTED — runner output attached |
| test_global_source_authority_v29_7_3 | BLOCKED: pytest unavailable |
| ۱۶) HTML Process V26.15 | EXECUTED — runner output attached |
| test_html_payload_compaction_v285 | BLOCKED: pytest unavailable |
| ۷) سیستمی و استقرار | EXECUTED — runner output attached |
| test_knowledge_desk_offline_v292 | BLOCKED: pytest unavailable |
| test_knowledge_desk_self_index_guard_v2946 | BLOCKED: pytest unavailable |
| test_knowledge_desk_static_v293 | BLOCKED: pytest unavailable |
| ۱۹) انتقال دانش نسل قدیم V26.19 | EXECUTED — runner output attached |
| test_material_dashboard_runtime_v29_6_8 | BLOCKED: pytest unavailable |
| test_material_group_identity_v29_6_6 | BLOCKED: pytest unavailable |
| test_material_html_advisory_only_v29_6_7 | BLOCKED: pytest unavailable |
| test_material_html_export_v29_6_1 | BLOCKED: pytest unavailable |
| test_material_html_export_v29_6_2 | BLOCKED: pytest unavailable |
| test_material_html_export_v29_6_3 | BLOCKED: pytest unavailable |
| test_material_runtime_visible_v29_6_4 | BLOCKED: pytest unavailable |
| test_material_source_boundary_v29_6_9 | BLOCKED: pytest unavailable |
| test_material_source_search_v2950 | BLOCKED: pytest unavailable |
| test_material_supply_html_v29_6_5 | BLOCKED: pytest unavailable |
| ۱۸) برج کنترل جریان پول V26.18 | EXECUTED — runner output attached |
| test_money_flow_v29_6 | BLOCKED: pytest unavailable |
| ۲۶) خطاهای شبکه و ذخیره‌سازی | EXECUTED — runner output attached |
| ۱۴) Oracle چندشیتی V26.14 | EXECUTED — runner output attached |
| test_oracle_union_v28_1 | EXECUTED — runner output attached |
| ۲۵) فضای شخصی رمزگذاری‌شده و Snapshot بدون IP | EXECUTED — runner output attached |
| test_population_cashflow_v29_7_4 | BLOCKED: pytest unavailable |
| test_process_cockpit_v28 | BLOCKED: pytest unavailable |
| test_process_integrity_v29_7_5 | BLOCKED: pytest unavailable |
| ۱۱) سازنده گزارش و صحت دانه‌ای | EXECUTED — runner output attached |
| test_report_composer_tab_isolation_v284 | BLOCKED: pytest unavailable |
| test_report_composer_v28 | BLOCKED: pytest unavailable |
| ۲) کتابخانه قوانین و سورس مقاومت | EXECUTED — runner output attached |
| ۲۸) رفع خطای زمان اجرا | EXECUTED — runner output attached |
| test_sap_semantic_dwh_v29_7_6 | BLOCKED: pytest unavailable |
| ۱۰) GSI Studio ماژولار | EXECUTED — runner output attached |
| ۱۵) Studio V26.12 | EXECUTED — runner output attached |
| ۱۲) حوزه مسئولیت، مالکیت قطعه و نماهای تأمین | EXECUTED — runner output attached |
| ۱۳) نقاط کور سیستمی و فرآیندی | EXECUTED — runner output attached |
| ۲۳) برداری‌سازی ۳۸، سامانه انبار، پنجره اعتبار قوانین | EXECUTED — runner output attached |
| ۲۰) صف تخصیص، اقدام پرونده و موجودی V26.20 | EXECUTED — runner output attached |
| ۲۱) runtime مرورگر، دانه موجودی و COM اوت‌لوک | EXECUTED — runner output attached |
| ۲۴) مخاطب، لحن و صداقت خروجی | EXECUTED — runner output attached |
| test_v29_4_1_runtime_diagnostics | BLOCKED: pytest unavailable |
| test_v29_4_2_diagnose_business_semantics | BLOCKED: pytest unavailable |
| test_v29_4_3_relation_health_contract | BLOCKED: pytest unavailable |
| test_v29_4_4_streamlit_load_performance | BLOCKED: pytest unavailable |
| test_v29_4_5_import_license_continuity | BLOCKED: pytest unavailable |
| test_v29_4_7_multi_pr_and_chatbot | BLOCKED: pytest unavailable |
| test_v29_4_8_sqlite_reader_isolation | BLOCKED: pytest unavailable |
| test_v29_4_9_material_text_search | BLOCKED: pytest unavailable |
| test_v29_4_resilience_editorial | BLOCKED: pytest unavailable |
| test_v29_business_dwh | BLOCKED: pytest unavailable |
| test_v29_reliability_gate | BLOCKED: pytest unavailable |
| ۱) الگوریتمی و بیزینسی | EXECUTED — runner output attached |
| ۲۹) دیتاورهوس و مخاطبان V28 | EXECUTED — runner output attached |

## 6. Inventory تمام تست‌های بسته

شمارش declarations شامل helper/test functionهای AST است و معادل تعداد موارد parametrized runtime نیست. legacy_testها در discovery استاندارد test_*.py runner وارد نمی‌شوند؛ نام‌ها اینجا همچنان فهرست شده‌اند.

| File | Test declarations | Entry mode / coverage identifiers |
|---|---:|---|
| `tests/conftest.py` | 0 | pytest / helper;  |
| `tests/legacy_test_html_browser_v26_17.py` | 0 | standalone script;  |
| `tests/legacy_test_v26_16_hardening.py` | 4 | standalone script; `test_unique_large_amounts_are_not_identifiers`, `test_html_honors_visuals_tables_without_silent_payload_cap`, `test_scope_is_applied_before_html_embedding`, `test_pipeline_commitment_kpi_is_grain_safe` |
| `tests/legacy_test_v26_16_release.py` | 0 | standalone script;  |
| `tests/legacy_test_v26_18_charts_delivery_persistence.py` | 0 | standalone script;  |
| `tests/legacy_test_warehouse_v26_17.py` | 0 | standalone script;  |
| `tests/make_synthetic.py` | 0 | pytest / helper;  |
| `tests/test_anythingllm_learning_v29.py` | 3 | pytest / helper; `test_public_embed_never_exposes_api_key`, `test_html_weekly_lesson_and_embed_are_optional_and_safe`, `test_html_without_embed_stays_offline_for_qa` |
| `tests/test_architecture.py` | 6 | standalone script; `test_stage_contract`, `test_order_guard`, `test_add_remove_feature`, `test_version_skew`, `test_eventlog`, `test_thin_orchestrator` |
| `tests/test_cashflow_dwh_v29_7_2.py` | 2 | pytest / helper; `test_pipeline_bridge_no_longer_quarantines_every_dwh_fact`, `test_native_dwh_prefers_ntsw_and_commercial_expert_over_sata` |
| `tests/test_cashflow_hardening_v29_7_1.py` | 5 | pytest / helper; `test_reversed_payment_links_are_not_counted`, `test_source_replay_account_conflict_is_quarantined`, `test_payment_and_obligation_links_have_separate_capacity`, `test_snapshot_conflict_and_date_gap`, `test_transfer_reversal_does_not_create_external_cashflow` |
| `tests/test_cashflow_v29_7.py` | 33 | pytest / helper; `test_exact_cash_and_opening`, `test_missing_opening_is_not_zero`, `test_duplicate_payment_does_not_fanout`, `test_conflicting_payment_quarantines_all_versions`, `test_invalid_cash_does_not_count`, `test_noncash_does_not_spend_money`, `test_unlinked_settlement_never_reduces_obligation`, `test_snapshot_is_reconciliation_not_event`, `test_repeated_snapshots_do_not_multiply_balance`, `test_reversal_is_immutable_opposite_cash_event`, `test_bad_reversal_is_quarantined`, `test_source_event_id_replay_and_conflict`, `test_cross_currency_obligation_needs_basis_and_authorization`, `test_toman_is_never_silently_treated_as_rial`, `test_currencies_never_added`, `test_refund_not_automatic_commitment_release`, `test_allocation_and_quota_excess`, `test_fx_requires_both_legs`, `test_links_split_payment_and_preserve_capacity`, `test_overallocation_never_clamped_or_hidden`, `test_cross_case_needs_authorization`, `test_rates_historical_no_future_no_mixed_purpose`, `test_exact_documented_fx_valuation`, `test_rate_conflict_blocks_valuation`, `test_old_pdf_rule_not_applied`, `test_of_missing_payment_ids_never_becomes_cash`, `test_html_and_excel_safely_escape_and_keep_long_ids`, `test_transfer_does_not_inflate_period_cash`, `test_cash_links_need_actual_account_and_currency_path`, `test_rate_regime_must_match`, `test_invalid_report_date_rejected`, `test_partial_bl_and_customs_currency_remain_distinct`, `test_dashboard_financial_panel_build_and_scope` |
| `tests/test_cluster_scope_v284.py` | 4 | pytest / helper; `test_expert_cluster_scope_is_self_only`, `test_manager_cluster_scope_is_active_experts_plus_self`, `test_executive_cluster_scope_is_all_active_cluster_members`, `test_explicit_scope_augments_cluster_scope` |
| `tests/test_contracts_report.py` | 4 | standalone script; `test_reproduce_user_bug`, `test_report_keys_exist`, `test_arithmetic_visible`, `test_sheet_not_blank` |
| `tests/test_control_center_v27_2.py` | 17 | standalone script; `test_defaults_revision_conflict`, `test_unknown_columns_not_in_config`, `test_drift_preserves_config`, `test_duplicate_identity`, `test_duplicate_header`, `test_partial_invalid_file`, `test_raw_archive_and_idempotency`, `test_missing_rows_preserved`, `test_xlsx_codes`, `test_cluster_import_keeps_template`, `test_membership_integrity`, `test_inactive_member`, `test_template_rejects_attribute_access`, `test_personal_store_unchanged_on_export`, `test_snapshot_required`, `test_draft_never_sends`, `test_restore_revision` |
| `tests/test_criticality.py` | 6 | standalone script; `test_engine`, `test_combined_alerts`, `test_pipeline`, `test_excel`, `test_configurable`, `test_group_criticality` |
| `tests/test_dashboard.py` | 8 | standalone script; `test_metrics`, `test_cards`, `test_export_html`, `test_columns`, `test_dashboard_module`, `test_scorecard_group_criticality`, `test_regressions_v26_2_3`, `test_email_from_hr` |
| `tests/test_dashboard_criticality_repair_v28.py` | 3 | pytest / helper; `test_unknown_bands_are_repaired_from_official_resistance`, `test_existing_valid_band_is_not_overwritten`, `test_dashboard_and_cockpit_counts_follow_repaired_band` |
| `tests/test_design_system.py` | 0 | standalone script;  |
| `tests/test_doc_claims.py` | 3 | standalone script; `test_readme_numbers`, `test_version_single_source`, `test_factsheet_runs` |
| `tests/test_email_report.py` | 0 | standalone script;  |
| `tests/test_fullstack_v29_6_10.py` | 9 | pytest / helper; `test_empty_scope_never_leaks_process_or_fx`, `test_scope_keys_do_not_match_other_identity_types`, `test_missing_department_column_does_not_expand_scope`, `test_column_scope_blocks_material_and_hidden_fields`, `test_oracle_resistance_survives_advisory_boundary`, `test_real_dashboard_runs_through_html_download`, `test_financial_card_deduplicates_and_never_adds_currencies`, `test_historical_material_status_uses_report_date`, `test_studio_starts_with_published_snapshot` |
| `tests/test_fx_adapter_quarantine_v28.py` | 2 | pytest / helper; `test_fx_invalid_amount_is_quarantined_not_fatal`, `test_fx_orphan_and_invalid_reasons_both_preserved` |
| `tests/test_fx_obligation_v28_1.py` | 8 | standalone script; `test_matched_registration_closes_the_chain`, `test_unmatched_chain_is_reported_not_hidden`, `test_missing_amount_is_unknown_never_zero`, `test_a_real_zero_balance_stays_zero`, `test_currencies_are_never_summed_together`, `test_decimal_precision_survives`, `test_blank_source_row_is_not_a_case`, `test_stage_without_evidence_is_unknown_not_done` |
| `tests/test_fx_traceability_v26_16.py` | 5 | standalone script; `test_fx_ledger_is_reg_grain_and_no_fanout`, `test_obligations_are_separate_not_one_boolean`, `test_conformance_names_match_eventlog_and_order_uses_position`, `test_current_rule_snapshot_present`, `test_html_process_explorer_embeds_fx_traceability` |
| `tests/test_global_source_authority_v29_7_3.py` | 9 | pytest / helper; `test_policy_is_full_report_and_primary_sources_are_expert_ntsw`, `test_canonical_conflict_uses_expert_over_abbasi_and_oracle`, `test_canonical_reg_uses_ntsw_over_sata`, `test_derived_global_sort_primary_then_secondary_then_fallback`, `test_derive_stage_applies_policy_to_whole_report_fields`, `test_secondary_only_fills_primary_blank`, `test_order_format_cannot_override_higher_authority_expert`, `test_ntsw_reg_file_hub_builds_primary_order_reg_without_sata`, `test_full_report_base_uses_ntsw_reg_over_conflicting_sata` |
| `tests/test_html_export_v26_15.py` | 2 | standalone script; `test_dynamic_html_has_story_process_and_excel`, `test_inline_json_cannot_break_script_context` |
| `tests/test_html_payload_compaction_v285.py` | 2 | pytest / helper; `test_main_payload_is_row_array_not_repeated_record_objects`, `test_process_runtime_does_not_duplicate_eventlog_or_action_queue` |
| `tests/test_import_hygiene.py` | 6 | standalone script; `test_no_stdlib_collision`, `test_reproduce_and_fix`, `test_runs_from_any_cwd`, `test_entry_points`, `test_structure`, `test_no_hard_dependency` |
| `tests/test_knowledge_desk_offline_v292.py` | 3 | pytest / helper; `test_offline_kb_index_and_answer`, `test_html_uses_static_chatbot_without_http_api`, `test_native_http_service_chat` |
| `tests/test_knowledge_desk_self_index_guard_v2946.py` | 4 | pytest / helper; `test_generated_chatbot_is_never_lesson`, `test_exact_publish_source_overlap_blocked`, `test_empty_knowledge_does_not_publish_false_success`, `test_publish_child_of_knowledge_is_safe_and_not_reindexed` |
| `tests/test_knowledge_desk_static_v293.py` | 3 | pytest / helper; `test_static_bundle_zero_server_and_source_privacy`, `test_report_opens_static_chatbot_with_question`, `test_unc_path_to_file_uri` |
| `tests/test_legacy_knowledge_v26_19.py` | 3 | standalone script; `test_catalog_and_guard`, `test_runtime_signals`, `test_stage_and_rate_semantics` |
| `tests/test_material_dashboard_runtime_v29_6_8.py` | 1 | pytest / helper; `test_dashboard_style_call_auto_builds_material_advisory_tab` |
| `tests/test_material_group_identity_v29_6_6.py` | 2 | pytest / helper; `test_material_identity_is_key_not_description`, `test_material_description_is_separate_filterable_attribute` |
| `tests/test_material_html_advisory_only_v29_6_7.py` | 2 | pytest / helper; `test_expert_and_ntsw_are_advisory_only_in_html_material_view`, `test_material_html_payload_is_not_cut_before_search` |
| `tests/test_material_html_export_v29_6_1.py` | 1 | pytest / helper; `test_material_identity_is_kept_in_main_tab_table_even_if_saved_tab_omits_it` |
| `tests/test_material_html_export_v29_6_2.py` | 3 | pytest / helper; `test_no_global_static_material_supply_table_is_injected_above_tabs`, `test_high_cardinality_material_gets_tab_scoped_text_filter`, `test_material_filter_is_part_of_same_runtime_slice_as_table` |
| `tests/test_material_html_export_v29_6_3.py` | 2 | pytest / helper; `test_material_is_in_each_tab_and_each_tab_owns_filter`, `test_authoritative_version_bumped` |
| `tests/test_material_runtime_visible_v29_6_4.py` | 1 | pytest / helper; `test_html_exposes_build_and_material_filter_in_every_tab` |
| `tests/test_material_source_boundary_v29_6_9.py` | 7 | pytest / helper; `test_real_aliases_and_material_link_do_not_control_position`, `test_advisory_fanout_and_mutation_leave_operational_values_identical`, `test_excluded_dates_never_assign_next_activity_or_missing_date`, `test_old_precomputed_view_cannot_bypass_boundary`, `test_missing_material_and_duplicate_index_preserve_comment_alignment`, `test_expert_only_identity_is_not_operational_material`, `test_composer_financial_data_is_preserved` |
| `tests/test_material_source_search_v2950.py` | 2 | pytest / helper; `test_same_material_code_returns_all_rows_despite_description_pr_order_changes`, `test_material_identifier_is_text_and_supports_letters_and_persian_digits` |
| `tests/test_material_supply_html_v29_6_5.py` | 1 | pytest / helper; `test_html_contains_one_filterable_material_supply_tab` |
| `tests/test_money_flow_v26_18.py` | 4 | standalone script; `test_rate_bridge`, `test_reallocation`, `test_stage_timeline_and_deadline`, `test_intelligence_registry` |
| `tests/test_money_flow_v29_6.py` | 3 | pytest / helper; `test_end_to_end_money_ledger_preserves_grain_and_unknown`, `test_same_currency_reconciliation_and_obligation_equation`, `test_supplier_receipt_closes_swift_conversion_stage_evidence` |
| `tests/test_network_outlook_debugged.py` | 18 | standalone script; `test_old_lock_is_not_stolen`, `test_lock_owner_change_is_preserved`, `test_failed_replace_preserves_previous`, `test_transient_sharing_violation_retries`, `test_client_cannot_publish`, `test_invalid_kind_rejected`, `test_future_schema_rejected`, `test_network_disappearance_is_not_empty`, `test_utf16_key_file`, `test_base64_junk_rejected`, `test_nonfinite_json_cleaned`, `test_unknown_columns_never_leak`, `test_invalid_limit_rejected`, `test_action_fields_preserved`, `test_explicit_empty_scope_clears_previous`, `test_bad_preferences_rejected`, `test_preferences_do_not_share_mutable_defaults`, `test_snapshot_context_consistent` |
| `tests/test_oracle_multisheet_v26_14.py` | 1 | standalone script; `test_oracle_merges_two_sheets_preferring_full_data` |
| `tests/test_oracle_union_v28_1.py` | 7 | standalone script; `test_no_part_is_dropped_when_sheets_are_disjoint`, `test_source_sheet_is_recorded_for_every_row`, `test_excluded_headers_never_reach_the_output`, `test_missing_quantity_stays_missing_not_zero`, `test_overlapping_part_uses_one_sheet_only_no_hybrid`, `test_duplicate_inside_one_sheet_resolves_at_material_grain`, `test_exact_duplicate_business_row_is_not_double_counted` |
| `tests/test_personalization_v27_1.py` | 32 | standalone script; `test_employee_folder_is_canonical_eight_digits`, `test_profile_persists_between_store_instances`, `test_encrypted_file_does_not_expose_plaintext`, `test_snapshot_is_separate_from_profile`, `test_snapshot_replace_drops_stale_keys`, `test_wrong_key_fails_closed`, `test_tamper_is_detected`, `test_user_isolation_uses_distinct_crypto_context`, `test_integrity_check`, `test_audit_does_not_store_value`, `test_per_user_key_can_open_only_its_user_store`, `test_from_env_prefers_user_key_without_master`, `test_master_key_file_must_not_be_inside_profile_root`, `test_identity_resolution_never_uses_ip`, `test_identity_fails_closed_when_missing`, `test_workspace_defaults_and_saved_preferences`, `test_local_config_restores_root_identity_and_user_key_without_env`, `test_central_publish_fails_closed_without_master_even_if_user_key_exists`, `test_windows_installer_uses_local_launcher_and_recommends_key_file`, `test_publish_scopes_each_user`, `test_personal_html_has_local_live_protocol_not_http_api`, `test_launcher_renders_from_shared_store_to_local_cache`, `test_personal_html_reads_shared_store_and_keeps_preferences`, `test_shared_files_are_only_encrypted_store_files`, `test_numpy_bool_stays_boolean`, `test_audience_caps_reach_the_personal_html`, `test_namespace_and_get_share_one_error_contract`, `test_broken_user_key_is_not_reported_as_master_key`, `test_vanished_share_gives_an_actionable_error`, `test_atomic_write_retries_before_giving_up`, `test_doctor_checks_the_shared_store`, `test_handoff_points_at_the_real_figma_file` |
| `tests/test_population_cashflow_v29_7_4.py` | 6 | pytest / helper; `test_primary_population_is_expert_plus_ntsw_not_abbasi`, `test_one_primary_order_can_keep_multiple_abbasi_bls_without_abbasi_population`, `test_ntsw_only_primary_row_is_main_population_not_to_resolve`, `test_cashflow_chain_exposes_missing_funding_and_settlement_without_inference`, `test_complete_obligation_link_reconciles_remaining_commitment`, `test_dwh_same_fx_source_row_creates_documented_purchase_to_payment_link` |
| `tests/test_process_cockpit_v28.py` | 4 | pytest / helper; `test_critical_materials_unique_and_sorted`, `test_stage_counts_use_latest_real_event`, `test_owner_and_quality_unknown_not_zero`, `test_action_board_priority_order` |
| `tests/test_process_integrity_v29_7_5.py` | 6 | pytest / helper; `test_sap_preserves_workflow_history_and_latest_projection`, `test_later_stage_never_hides_missing_predecessor`, `test_sap_only_pr_is_kept_in_process_inventory_without_entering_flat_population_contract`, `test_attach_marks_ambiguous_instead_of_guessing`, `test_tolerant_stage_exception_does_not_stop_independent_flow`, `test_keyless_source_row_is_preserved_as_orphan_evidence` |
| `tests/test_report_builder.py` | 6 | standalone script; `test_fanout_double_counting`, `test_measure_kind`, `test_integrity_report`, `test_html_export`, `test_templates_build`, `test_cross_format_consistency` |
| `tests/test_report_composer_tab_isolation_v284.py` | 4 | pytest / helper; `test_legacy_global_charts_migrate_only_to_first_tab`, `test_html_tabs_are_structurally_isolated`, `test_process_and_actions_follow_authorized_scope`, `test_timeline_has_local_escape_runtime` |
| `tests/test_report_composer_v28.py` | 3 | pytest / helper; `test_tab_blocks_keep_author_order`, `test_html_composer_process_kanban_order_and_header`, `test_saved_design_persists_layout_persona_headers` |
| `tests/test_rules_and_moghavemat.py` | 8 | standalone script; `test_rulebook`, `test_bl_validation`, `test_status_lexicon`, `test_order_ref`, `test_moghavemat`, `test_modularity`, `test_excel`, `test_key_registry` |
| `tests/test_runtime_v27_2_1.py` | 7 | standalone script; `test_new_median`, `test_legacy_mean`, `test_missing_metric`, `test_invalid_not_zero`, `test_resistance_reasons`, `test_empty_filter`, `test_config_without_crypto` |
| `tests/test_sap_semantic_dwh_v29_7_6.py` | 3 | pytest / helper; `test_sap_adapter_separates_business_grains_and_normalizes_dates`, `test_business_dwh_persists_sap_facts_and_direct_pr_po_relations`, `test_operational_chatbot_reads_published_semantic_dwh` |
| `tests/test_studio.py` | 0 | standalone script;  |
| `tests/test_studio_v26_12.py` | 2 | standalone script; `test_transport`, `test_tabs_and_design` |
| `tests/test_supply_views.py` | 6 | standalone script; `test_scopes`, `test_status`, `test_commercial_coverage`, `test_views`, `test_performance`, `test_suite_registration` |
| `tests/test_system_health.py` | 7 | standalone script; `test_reader_fail_closed`, `test_health_registry`, `test_health_sheet`, `test_timeline_anomaly`, `test_material_lineage`, `test_coverage_states`, `test_runtime_hygiene` |
| `tests/test_v26_20_2_engine_hardening.py` | 3 | standalone script; `test_s38_vectorised`, `test_warehouse_declaration`, `test_rule_expiry` |
| `tests/test_v26_20_case_action_inventory.py` | 4 | standalone script; `test_unknown_not_zero`, `test_ntsw_request_ledger`, `test_pipeline_actions_identity`, `test_contracts` |
| `tests/test_v26_20_runtime_and_grain.py` | 0 | standalone script;  |
| `tests/test_v27_audience_and_voice.py` | 5 | standalone script; `test_profiles`, `test_voice`, `test_html_respects_audience`, `test_html_hides_what_is_not_for_the_reader`, `test_no_overclaiming_in_output` |
| `tests/test_v29_4_1_runtime_diagnostics.py` | 3 | pytest / helper; `test_busy_lock_has_precise_diagnostic`, `test_runtime_classifier_does_not_prescribe_doctor_for_busy`, `test_source_path_error_does_prescribe_doctor` |
| `tests/test_v29_4_2_diagnose_business_semantics.py` | 6 | pytest / helper; `test_reg_file_is_not_reg_and_ntsw_hub_is_used`, `test_sap_is_diagnosed_by_pr_but_excluded_while_source_is_known_incomplete`, `test_order_material_is_grain_contract_not_bl_join`, `test_order_material_duplicate_is_explicit_grain_violation`, `test_critical_diagnostic_uses_real_clearance_field_and_mogh_grains`, `test_derive_accepts_actual_clearance_adapter_column` |
| `tests/test_v29_4_3_relation_health_contract.py` | 6 | pytest / helper; `test_low_base_coverage_does_not_make_healthy_source_join_bad`, `test_incomplete_sap_is_informational_not_false_error`, `test_order_unmatched_breakdown_is_forensic_not_auto_match`, `test_mostly_matched_relation_is_info_not_error`, `test_zero_overlap_is_unproven_relation_not_claimed_bad_format`, `test_known_incomplete_zero_match_does_not_degrade_system_health` |
| `tests/test_v29_4_4_streamlit_load_performance.py` | 3 | pytest / helper; `test_last_report_loads_only_df_main_and_keeps_extras_lazy`, `test_persist_result_does_not_roundtrip_by_default`, `test_frame_cache_is_disposable_and_sqlite_remains_authoritative` |
| `tests/test_v29_4_5_import_license_continuity.py` | 4 | pytest / helper; `test_import_license_partial_blank_rows_warn_but_do_not_block`, `test_import_license_no_complete_bridge_blocks`, `test_quality_gate_exception_is_typed_and_preserves_current`, `test_runtime_classifier_quality_gate_does_not_prescribe_doctor` |
| `tests/test_v29_4_7_multi_pr_and_chatbot.py` | 3 | pytest / helper; `test_multi_pr_is_preserved_at_relation_grain`, `test_report_html_renders_chatbot_without_optional_content`, `test_static_chatbot_does_not_use_weekly_wording` |
| `tests/test_v29_4_8_sqlite_reader_isolation.py` | 4 | pytest / helper; `test_lazy_extra_never_initializes_schema`, `test_cached_frame_reads_while_sqlite_has_exclusive_lock`, `test_locked_lazy_extra_degrades_without_crashing`, `test_last_report_reader_does_not_initialize_schema` |
| `tests/test_v29_4_9_material_text_search.py` | 3 | pytest / helper; `test_material_identifier_is_unicode_text`, `test_rows_168_170_keep_same_material_despite_description_change`, `test_quick_search_accepts_alphanumeric_material_and_separators` |
| `tests/test_v29_4_resilience_editorial.py` | 4 | pytest / helper; `test_last_published_standardized_frame_can_be_used_as_explicit_stale_fallback`, `test_noncritical_branch_failure_degrades_but_does_not_block_publish_gate`, `test_registration_spine_failure_blocks_publication_without_hiding_diagnostics`, `test_editorial_tokens_are_restrained_and_css_exposes_paper_language` |
| `tests/test_v29_business_dwh.py` | 3 | pytest / helper; `test_registration_file_hub_and_order_material_grain`, `test_moghavemat_does_not_create_bl_relation`, `test_order_material_pr_item_bridge_preserves_multiple_prs_and_evidence` |
| `tests/test_v29_reliability_gate.py` | 6 | pytest / helper; `test_order_material_grain_duplicate_blocks`, `test_order_material_distinct_material_is_valid`, `test_missing_key_column_blocks`, `test_atomic_publish_does_not_move_on_failed_gate`, `test_publish_moves_both_slots_together`, `test_schema_drift_is_visible_and_baseline_is_stable` |
| `tests/test_validation.py` | 6 | standalone script; `test_units`, `test_engines`, `test_narrator_guard`, `test_pipeline`, `test_excel`, `test_v25_fixes` |
| `tests/test_warehouse_v28.py` | 17 | standalone script; `test_frame_roundtrip`, `test_nonfinite_roundtrip`, `test_empty_frame`, `test_failed_run_not_published`, `test_blob_idempotent`, `test_hidden_formula_preserved`, `test_capture_rerun`, `test_no_network_db`, `test_wrong_database`, `test_backup`, `test_decimal`, `test_contacts_and_membership`, `test_contact_invalid_atomic`, `test_config_revision_audit_transaction`, `test_html_custom_fields_role_widgets`, `test_scope_does_not_expand_for_manager`, `test_explicit_scope` |

## 7. Doctor و محیط

اجرای doctor زیر در محیط ممیزی انجام شد. هشدار مسیرهای شبکه/قواعد به معنی اثبات خرابی deployment واقعی نیست.

```text
══════════════════════════════════════════════════════════════════════════════
GSI Doctor — بازرس نصب و محیط اجرا
══════════════════════════════════════════════════════════════════════════════
پوشه جاری: /workspace/scratch/783c44f5d0b8/audit/gsi_2976

── ۱) بررسی سایه‌اندازی روی کتابخانه استاندارد پایتون ──
✅ هیچ فایلی روی ماژول‌های استاندارد سایه نینداخته است (1 مسیر کاربر بررسی شد).

── ۲) بررسی هم‌نسخه بودن فایل‌های پکیج ──
   نسخه پکیج: 29.7.6
✅ تمام قراردادهای بین‌ماژولی سازگارند.
✅ اثر انگشت همه فایل‌ها با مانیفست رسمی می‌خواند.

── ۲.۵) بررسی گراف فرآیند ──
✅ 18 مرحله کشف و زنجیره علّی آن‌ها تأیید شد: resolve → derive → org → scope → supply_position → warehouse_declaration → criticality → commitment → process_integrity → fx_traceability → money_flow_control → legacy_knowledge_transfer → case_actions → narrate → risk → eventlog → conformance → sort

── ۳) بررسی ساختار پکیج ──
✅ هر 11 زیرپوشه پکیج موجود است (/workspace/scratch/783c44f5d0b8/audit/gsi_2976/gsi)
✅ تمام زیرپکیج‌ها __init__.py دارند.
✅ هیچ فایل پکیجی به‌صورت تخت رها نشده است.
✅ نسخه تک‌فایلی قدیمی gsi.py در مسیر نیست.

── ۴) بررسی کتابخانه‌ها ──
   پایتون 3.12.14 — /opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python
✅ pandas 2.2.3
✅ numpy 2.3.5
✅ openpyxl 3.1.5
✅ yaml 6.0.3
⚠️  jdatetime: نصب نیست — اختیاری — مبدل شمسی داخلی جایگزین آن است
✅ sklearn: نصب است — اختیاری — برای تشخیص آنومالی

── ۵) بررسی کتابخانه قوانین و رجیستری سورس‌ها ──
✅ 13 بسته قانونی سالم بارگذاری شد.
⚠️  23 قاعده نیازمند تطبیق با آخرین بخشنامه است (python -m gsi.rulebook.validate)
⚠️  انقضای نزدیک [fx_governance] regulatory_snapshot.emergency_deadline_overlay_1405_05_14: تمدید تا پایان شهریور ۱۴۰۵ برای مهلت‌هایی که قبلاً به علت شرایط اضطرار تمدید شده‌اند — 0 روز تا انقضا (2026-09-22)؛ تمدید یا جانشین را پیش از این تاریخ ثبت کنید.
⚠️  انقضای نزدیک [customs] emergency_sata_waiver_1405: ترخیص بدون کد ساتا با تعهد EPL (تسهیل اضطراری ۱۴۰۵) — 0 روز تا انقضا (2026-09-22)؛ تمدید یا جانشین را پیش از این تاریخ ثبت کنید.
✅ 13 adapter کشف شد برای 13 سورس فعال.

── ۶) بررسی دسترسی به مسیرهای شبکه ──
⚠️  abbasi          پوشه در دسترس نیست — \\ikco.com\data-share\Global Sourcing\03-Data\01-Foreign\BLs TOTAL
⚠️  moghavemat      پوشه در دسترس نیست — \\ikco.com\data-share\Global Sourcing\11-Governance & Integration\DataTeam\Data_Ware_House\GS_Combine\OUTPUT
⚠️  clearance       پوشه در دسترس نیست — \\ikco.com\data-share\Global Sourcing\03-Data\01-Foreign\BLs TOTAL\Clearance
⚠️  ntsw            پوشه در دسترس نیست — \\ikco.com\data-share\Global Sourcing\03-Data\01-Foreign
⚠️  doccheck        پوشه در دسترس نیست — \\ikco.com\data-share\Global Sourcing\11-Governance & Integration\26-M.Mohamadi
⚠️  hr              پوشه در دسترس نیست — \\ikco.com\data-share\Global Sourcing\11-Governance & Integration\03-Reports\01-HR
✅ مسیر خروجی قابل نوشتن است: /root/.gsi/output
✅ مسیر لاگ قابل نوشتن است: /root/.gsi/logs
✅ قفل نویسنده DWH آزاد است.

── ۷) بررسی Store شخصی روی پوشه مشترک ──
⚠️  GSI_PROFILE_ROOT تنظیم نشده است — Store شخصی و publish-personal کار نمی‌کنند.

══════════════════════════════════════════════════════════════════════════════
نتیجه: 0 خطا | 11 هشدار
✅ محیط سالم است. اکنون اجرا کنید:  python -m gsi.pipeline
💡 اگر KPIها صفر یا غیرمنطقی بودند، اول این را بزنید:
   python -m gsi.diagnose --excel     ← می‌گوید کدام رابطه برقرار نشده
══════════════════════════════════════════════════════════════════════════════

```

## 8. بازاجرای شواهد

```bash
# From the delivered evidence bundle root, after placing/extracting the unchanged input ZIP
# to audit/gsi_2976 (as used by the harness):
PYTHONDONTWRITEBYTECODE=1 python evidence/probes.py
PYTHONDONTWRITEBYTECODE=1 python evidence/more_probes.py
PYTHONDONTWRITEBYTECODE=1 python evidence/final_probes.py
# Existing test runner from the package root; pytest must be installed:
GSI_DWH_PATH=/absolute/isolated/test.sqlite python run_all_tests.py
```

هر بازتولید باید روی DB آزمایشی تازه اجرا شود؛ probe.sqlite را از اجرای قبلی reuse نکنید. فایل اصلی ZIP باید با hash baseline تطبیق داده شود. این harness یک test suite محصول نیست و تغییر source لازم ندارد.
