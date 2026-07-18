from app.insights.impact import classify_impact


def test_classify_impact_critical_area_keyword():
    assert classify_impact("Payment retry loop double-charges card") == "high"
    assert classify_impact("Login page crashes on submit") == "high"
    assert classify_impact("Boarding pass QR code renders blank") == "high"


def test_classify_impact_cosmetic_keyword():
    assert classify_impact("Logo color slightly off on the header") == "low"
    assert classify_impact("Fix font spacing on the footer") == "low"


def test_classify_impact_no_match_returns_none():
    assert classify_impact("Table column width slightly narrow") is None
    assert classify_impact("") is None
    assert classify_impact(None) is None


def test_classify_impact_critical_keyword_wins_over_cosmetic_when_both_present():
    # "login" (critical) should win even if a cosmetic word also appears
    assert classify_impact("Login button color is wrong") == "high"
