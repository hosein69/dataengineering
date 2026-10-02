"""Independent smoke checks for the warehouse grain remediation (stdlib unittest)."""
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from unittest.mock import patch
import os

from gsi.config.sources import get_source
from gsi.dataio.reader import find_files
from gsi.warehouse.business_dwh import _entity_key, _fact_rows, merge_versions
from gsi.warehouse.reliability import validate_frame
from tools.source_variant_review import review
from tools.gsi_grain_speed_audit import inspect,clearance_inventory


class GrainRemediationTest(unittest.TestCase):
    def test_expert_main_material_key_matches_line_grain(self):
        from gsi.adapters.moghavemat import EXPERT_HEADERS, MoghavematAdapter
        fields = {field: header for field, header in EXPERT_HEADERS}
        source = pd.DataFrame([
            {fields['ORDER_REF']: '602164A', fields['MATERIAL']: 'PA-001', fields['ROW_NO']: '1'},
            {fields['ORDER_REF']: '602164A', fields['MATERIAL']: 'PA-002', fields['ROW_NO']: '2'},
            {fields['ORDER_REF']: '', fields['MATERIAL']: 'PA-003', fields['ROW_NO']: '3'},
        ], columns=list(fields.values())).fillna('')
        output = MoghavematAdapter().transform({'main': source})
        main = output['main']
        self.assertEqual(set(zip(main['KEY_ORDER'], main['KEY_MATERIAL'])), {
            ('602164A', 'PA001'), ('602164A', 'PA002'), ('', 'PA003')})
        checks = validate_frame('moghavemat/main', main)
        self.assertTrue(next(c for c in checks if c.code == 'REQUIRED_COLUMNS').passed)
        self.assertTrue(next(c for c in checks if c.code == 'GRAIN_UNIQUENESS').passed)

    def test_reference_keys_and_placeholders(self):
        self.assertEqual(_entity_key("ORDER", "842615-"), "842615")
        self.assertEqual(_entity_key("ORDER", "بدون سفارش"), "")
        self.assertEqual(_entity_key("REG_FILE", "0"), "")
        self.assertEqual(_entity_key("MATERIAL", "PA16-64-950R012"), "PA1664950R012")
        self.assertEqual(_entity_key("BL", "010000160188"), "010000160188")

    def test_explicit_source_file_selection(self):
        with TemporaryDirectory() as directory:
            for name in ("BLs Tracking.xlsx", "_Bls_Tracking_Managers.xlsx"):
                Path(directory, name).touch()
            spec = replace(get_source("abbasi"), folder=directory)
            self.assertEqual([Path(p).name for p in find_files(spec)], ["BLs Tracking.xlsx"])

    def test_external_source_registry_cannot_switch_expert_to_temp(self):
        with TemporaryDirectory() as directory:
            for name in ('Commercial Expert Data.xlsx', 'TEMP_Commercial Expert Data.xlsx'):
                Path(directory, name).touch()
            base = get_source('moghavemat')
            without_pin = replace(base, folder=directory, extra={})
            self.assertEqual([Path(p).name for p in find_files(without_pin)],
                             ['Commercial Expert Data.xlsx'])
            wrong_pin = replace(base, folder=directory,
                                extra={'file_names': ['TEMP_Commercial Expert Data.xlsx']})
            with self.assertRaisesRegex(ValueError, 'BASE_SOURCE_CONTRACT'):
                find_files(wrong_pin)
            Path(directory, 'Commercial Expert Data.xlsx').unlink()
            self.assertEqual(find_files(without_pin, quiet=True), [])

    def test_variant_is_inspected_but_never_selected_for_publication(self):
        with TemporaryDirectory() as directory:
            pd.DataFrame({"بارنامه": ["BL10001"], "شماره سفارش": ["602164A"]}).to_excel(
                Path(directory, "BLs Tracking.xlsx"), sheet_name="BLs Tracking", index=False)
            pd.DataFrame({"بارنامه": ["BL10002"], "شماره سفارش": ["602164B"]}).to_excel(
                Path(directory, "_Bls_Tracking_Managers.xlsx"), sheet_name="Sheet1", index=False)
            spec = replace(get_source("abbasi"), folder=directory)
            with patch("tools.source_variant_review.get_source", return_value=spec):
                result = review("abbasi")
            self.assertTrue(result["base_usable"])
            self.assertEqual({e["file"]: e["role"] for e in result["files"]}, {
                "BLs Tracking.xlsx": "BASE", "_Bls_Tracking_Managers.xlsx": "VARIANT_REVIEW_ONLY",
            })
            self.assertEqual([Path(p).name for p in find_files(spec)], ["BLs Tracking.xlsx"])

    def test_conflicting_fact_grain_is_rejected(self):
        rows = pd.DataFrame([
            {"KEY_ORDER": "602164A", "KEY_MATERIAL": "M1", "Q": 1},
            {"KEY_ORDER": "602164A", "KEY_MATERIAL": "M1", "Q": 2},
        ])
        with self.assertRaisesRegex(ValueError, "DWH_FACT_GRAIN_CONFLICT"):
            _fact_rows("dwh_fact_supply_position", rows)
        checks = validate_frame("moghavemat/main", rows)
        self.assertTrue(any(c.code == "GRAIN_UNIQUENESS" and not c.passed for c in checks))

    def test_version_merge_rejects_conflicting_rows_before_write(self):
        with self.assertRaisesRegex(ValueError, "DWH_VERSION_GRAIN_CONFLICT"):
            merge_versions(None, "dwh_fact_ntsw_commitment",
                           [("12345678", "one"), ("12345678", "two")], 1, "run")

    def test_abbasi_archive_defers_auxiliary_sheets_but_keeps_original_bytes(self):
        from gsi.warehouse.excel import capture
        from gsi.warehouse.store import Warehouse
        with TemporaryDirectory() as directory:
            p=Path(directory,'BLs Tracking.xlsx')
            with pd.ExcelWriter(p) as writer:
                pd.DataFrame({'بارنامه':['BL10001']}).to_excel(writer,sheet_name='BLs Tracking',index=False)
                pd.DataFrame({'helper':[1,2]}).to_excel(writer,sheet_name='DATES',index=False)
            with patch.dict(os.environ,{'GSI_DWH_PATH':str(Path(directory,'warehouse.sqlite'))}):
                fid,original,_=capture(p,'abbasi',keep_sheets=False,archive_sheets=['BLs Tracking'])
                self.assertEqual(original,p.read_bytes())
                wh=Warehouse()
                with wh.db() as c:
                    names={r[0] for r in c.execute('SELECT name FROM wh_sheet WHERE file_id=?',(fid,))}
                self.assertEqual(names,{'BLs Tracking'})
                capture(p,'abbasi',keep_sheets=False)  # forensic backfill, same file SHA
                with wh.db() as c:
                    names={r[0] for r in c.execute('SELECT name FROM wh_sheet WHERE file_id=?',(fid,))}
                self.assertEqual(names,{'BLs Tracking','DATES'})

    def test_diagnostic_excel_contains_timed_stages(self):
        with TemporaryDirectory() as directory:
            p=Path(directory,'BLs Tracking.xlsx')
            pd.DataFrame({'بارنامه':['BL10001'],'شماره سفارش':['602164A']}).to_excel(
                p,sheet_name='BLs Tracking',index=False)
            files=[];timings=[];frames=[];conflicts=[]
            inspect(p,'abbasi','VARIANT_REVIEW_ONLY',files,timings,frames,conflicts)
            self.assertEqual(files[0][11],'OK')
            self.assertIn('pandas_parse_contracted',{row[3] for row in timings})
            q=Path(directory,'_Bls_Tracking_Managers.xlsx')
            pd.DataFrame({'بارنامه':['BL10002']}).to_excel(q,sheet_name='Sheet1',index=False)
            inspect(q,'abbasi','VARIANT_REVIEW_ONLY',files,timings,frames,conflicts)
            self.assertEqual(files[1][11],'REVIEW_ONLY_NONCONTRACTED_SHEET')
            self.assertIn('بارنامه',files[1][12])

    def test_export_clearance_stays_out_of_import_relation(self):
        from gsi.dataio.reader import _read_targets
        from gsi.adapters.a30_customs import ClearanceAdapter
        from gsi.warehouse.business_dwh import _source_evidence
        with TemporaryDirectory() as directory:
            imp=Path(directory,'Sea Clearance.xlsx')
            exp=Path(directory,'Export Clearance.xlsx')
            columns={'بارنامه':['BL10001'],'پرونده ترخیص':['C1'],'شماره سفارش':['602164A']}
            pd.DataFrame(columns).to_excel(imp,sheet_name='Sea Clearance',index=False)
            pd.DataFrame(columns).to_excel(exp,sheet_name='Sheet1',index=False)
            spec=replace(get_source('clearance'),folder=directory)
            raw=_read_targets(spec,[str(imp),str(exp)])
            self.assertEqual(len(raw['main']),1)
            self.assertEqual(len(raw['export']),1)
            with patch('gsi.adapters.base.get_source',return_value=spec):
                transformed=ClearanceAdapter().transform(raw)
            self.assertEqual(len(transformed['main']),1)
            self.assertEqual(len(transformed['export']),1)
            _,relations,_,_,_=_source_evidence({'clearance':transformed})
            self.assertEqual(sum(relations.values()),1)  # one import ORDER ↔ BL
            rows=[]
            with patch('gsi.dataio.reader.source_targets',return_value=(spec,[str(imp),str(exp)])):
                clearance_inventory(rows)
            self.assertEqual([r[2] for r in rows],['IMPORT_MAIN','EXPORT_REVIEW_ONLY'])


if __name__ == "__main__":
    unittest.main()
