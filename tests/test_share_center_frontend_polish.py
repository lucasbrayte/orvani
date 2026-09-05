from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_card_separates_image_from_text_and_copy_button_confirms_success():
    css = (ROOT / "share_center/static/style.css").read_text(encoding="utf-8")
    js = (ROOT / "share_center/static/app.js").read_text(encoding="utf-8")

    assert "display:flex;flex-direction:column;isolation:isolate" in css
    assert "flex:0 0 260px" in css
    assert "overflow:hidden;position:relative;z-index:0" in css
    assert "position:relative;z-index:1;flex:1;background:var(--panel)" in css
    assert "border-top:1px solid var(--line)" in css

    assert "function showCopySuccess(control)" in js
    assert 'control.textContent = "✓ Copiado!";' in js
    assert 'control.classList.add("copy-success");' in js
    assert "showCopySuccess(control);" in js
    assert ".copy-success{" in css
    assert "@keyframes copy-confirm" in css
