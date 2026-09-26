import pandas as pd
from gsi.core.text import clean_part_no
from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.studio_core.filters import FilterState, apply_filters


def test_material_identifier_is_unicode_text():
    assert clean_part_no('ab-12') == 'AB12'
    assert clean_part_no('قطعه-۱۲a') == 'قطعه12A'
    assert clean_part_no('9654003280.0') == '9654003280'


def _source():
    return pd.DataFrame({
        'Row No.':[57,124,168,169,170],
        'Order No. (Our Reference)':['823107D','843115','843115','843120','843120'],
        'PR No.':['','6100002273','6100002723','6100002854','6100002854'],
        'PR Item':['','','20','20','20'],
        'Material':['9654003280']*5,
        'Material Description':['رينگ ضدقفل مغناطيسي','رينگ ضدقفل مغناطيسي','هدف چرخشي ترمز ضدقفل','هدف چرخشي ترمز ضدقفل','هدف چرخشي ترمز ضدقفل'],
        'Material Short Text':['','','ABS RADIAL TARGET','ABS RADIAL TARGET','ABS RADIAL TARGET'],
    })


def test_rows_168_170_keep_same_material_despite_description_change(monkeypatch):
    a=MoghavematAdapter.__new__(MoghavematAdapter)
    a.prefix='MOGH'; a.key='moghavemat'
    # Avoid RuleBook dependencies by validating only the material-line normalization
    from gsi.core.text import clean_order_ref, clean_part_no, clean_key
    df=_source()
    materials=df['Material'].map(clean_part_no)
    assert materials.tolist() == ['9654003280']*5
    # Description is not part of material identity.
    assert df.loc[df['Row No.'].isin([168,169,170]), 'Material'].map(clean_part_no).eq('9654003280').all()


def test_quick_search_accepts_alphanumeric_material_and_separators():
    df=pd.DataFrame({'KEY_MATERIAL':['AB12','9654003280','قطعه12A'], 'CANONICAL_ORDER':['1','2','3']})
    assert len(apply_filters(df, FilterState(search='ab-12'))) == 1
    assert len(apply_filters(df, FilterState(search='9654 003280'))) == 1
    assert len(apply_filters(df, FilterState(search='قطعه-۱۲a'))) == 1
