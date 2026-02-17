from homebrew_cdn_m1_server.application.gateways.pkgtool_gateway import (
    PkgtoolGateway,
    normalize_text,
)


def test_normalize_text_given_unicode_roman_numeral_then_converts_to_ascii() -> None:
    assert normalize_text("Final Fantasy \u2166") == "Final Fantasy VII"


def test_parse_sfo_entries_given_roman_numeral_title_then_stores_normalized_value() -> None:
    lines = [
        "TITLE : utf8 = Resident Evil \u2163",
        "TITLE_ID : utf8 = CUSA99999",
        "Entry Name : utf8 = TITLE",
    ]

    parsed = PkgtoolGateway.parse_sfo_entries(lines)

    assert parsed["TITLE"] == "Resident Evil IV"
    assert parsed["TITLE_ID"] == "CUSA99999"
    assert "Entry Name" not in parsed
