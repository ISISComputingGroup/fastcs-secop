from fastcs_secop import format_string_to_prec


def test_format_string_to_prec():
    assert format_string_to_prec("%.1f") == 1
    assert format_string_to_prec("%.99f") == 99
    assert format_string_to_prec("%.5g") is None
    assert format_string_to_prec("%.5e") is None
    assert format_string_to_prec(None) is None
