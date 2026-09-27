from app.localization import get_text

def test_get_text_fa():
    text = get_text("menu.buy_apple_id", "fa")
    assert "خرید" in text

def test_get_text_en():
    text = get_text("menu.buy_apple_id", "en")
    assert "Buy" in text

def test_missing_key_fallback():
    text = get_text("nonexistent_key", "fa")
    assert text == "nonexistent_key" or text == "None"