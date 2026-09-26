from gsi.rulebook import RuleBook


def test_ntsw_currency_label_with_repeated_whitespace_maps_to_iso():
    rb = RuleBook()
    assert rb.normalize_currency("ین  ژاپن ") == "JPY"
    assert rb.normalize_currency("یوان  چین ") == "CNY"


def test_currency_normalization_handles_arabic_persian_glyph_variants():
    rb = RuleBook()
    assert rb.normalize_currency("ين  ژاپن") == "JPY"
    assert rb.normalize_currency("درهم   امارات") == "AED"
