import pandas as pd
from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.warehouse.material_search import build_material_evidence, search_material


def test_same_material_code_returns_all_rows_despite_description_pr_order_changes():
    rows=[
        (57,'823107D','','',9654003280,'رينگ ضدقفل مغناطيسي',''),
        (124,'843115',6100002273,'',9654003280,'رينگ ضدقفل مغناطيسي',''),
        (168,'843115',6100002723,20,9654003280,'هدف چرخشي ترمز ضدقفل','ABS RADIAL TARGET'),
        (169,'843120',6100002854,20,9654003280,'هدف چرخشي ترمز ضدقفل','ABS RADIAL TARGET'),
        (170,'843120',6100002854,20,9654003280,'هدف چرخشي ترمز ضدقفل','ABS RADIAL TARGET'),
    ]
    df=pd.DataFrame(rows,columns=['Row No.','Order No. (Our Reference)','PR No.','PR Item','Material','Material Description','Material Short Text'])
    lines=MoghavematAdapter().transform({'Expert Data':df})['lines']
    evidence=build_material_evidence(lines)
    hits=search_material(evidence,'9654003280')
    assert hits['MOGH_ROW_NO'].astype(str).tolist() == ['57','124','168','169','170']
    assert set(hits['KEY_MATERIAL']) == {'9654003280'}


def test_material_identifier_is_text_and_supports_letters_and_persian_digits():
    lines=pd.DataFrame({
        'MOGH_ROW_NO':[1,2,3],
        'KEY_MATERIAL':['AB-12','قطعه-۱۲A','9654003280.0'],
    })
    evidence=build_material_evidence(lines)
    assert len(search_material(evidence,'ab12')) == 1
    assert len(search_material(evidence,'قطعه12a')) == 1
    assert len(search_material(evidence,'۹۶۵۴۰۰۳۲۸۰')) == 1
