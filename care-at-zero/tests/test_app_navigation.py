"""Headless smoke test using Streamlit's AppTest framework."""
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("../app.py")
at.run(timeout=20)

print("=== INITIAL LOAD (Home) ===")
print("Exceptions:", at.exception)
print("Buttons found:", [b.label for b in at.button])
print("Headers/subheaders:", [h.value for h in at.subheader])

assert not at.exception, f"App raised on initial load: {at.exception}"
assert "Home" in [b.label for b in at.button]
assert "Find" in [b.label for b in at.button]

# --- Click "Find" nav button ---
find_btn = [b for b in at.button if b.label == "Find"][0]
find_btn.click().run(timeout=20)
print("\n=== AFTER CLICKING Find ===")
print("Exceptions:", at.exception)
print("Subheaders:", [h.value for h in at.subheader])
assert not at.exception, f"App raised after clicking Find: {at.exception}"
assert any("Find Free or Low-Cost Care" in h.value for h in at.subheader)

# --- Check the search form widgets exist on Find page ---
print("Selectboxes:", [(sb.label) for sb in at.selectbox])
print("Text inputs:", [(ti.label) for ti in at.text_input])
assert any("When do you need care" in sb.label for sb in at.selectbox)
assert any("ZIP code" in ti.label for ti in at.text_input)
assert any("Select" in b.label or "Selected" in b.label for b in at.button)  # service picker cards present

# --- Click "Saved" nav button (empty state) ---
saved_btn = [b for b in at.button if b.label == "Saved"][0]
saved_btn.click().run(timeout=20)
print("\n=== AFTER CLICKING Saved ===")
print("Exceptions:", at.exception)
print("Info messages:", [i.value for i in at.info])
assert not at.exception, f"App raised after clicking Saved: {at.exception}"

# --- Click "About" nav button ---
about_btn = [b for b in at.button if b.label == "About"][0]
about_btn.click().run(timeout=20)
print("\n=== AFTER CLICKING About ===")
print("Exceptions:", at.exception)
print("Radio options:", [r.options for r in at.radio])
assert not at.exception, f"App raised after clicking About: {at.exception}"
assert any("Mission" in r.options for r in at.radio)

# --- Click "Detail" nav button with nothing selected yet ---
detail_btn = [b for b in at.button if b.label == "Detail"][0]
detail_btn.click().run(timeout=20)
print("\n=== AFTER CLICKING Detail (nothing selected) ===")
print("Exceptions:", at.exception)
print("Info messages:", [i.value for i in at.info])
assert not at.exception, f"App raised after clicking Detail: {at.exception}"

print("\n=== ALL CHECKS PASSED ===")
