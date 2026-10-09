"""Headless smoke test using Streamlit's AppTest framework.

Checks that every tab in the bottom tab bar (Home, Find, Help, About) opens
without errors and shows what it should.

Run from the tests folder:  python test_app_navigation.py
"""
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("../app.py")
at.run(timeout=20)


def labels():
    return [b.label for b in at.button]


def click(label):
    [b for b in at.button if b.label == label][0].click().run(timeout=20)
    assert not at.exception, f"App raised after clicking {label}: {at.exception}"


def page_text():
    return " ".join(m.value for m in at.markdown)


print("=== INITIAL LOAD (Home) ===")
assert not at.exception, f"App raised on initial load: {at.exception}"
for tab in ["Home", "Find", "Help", "About"]:
    assert tab in labels(), f"Bottom tab '{tab}' missing"
assert "Saved" not in labels(), "Saved tab should be gone (no accounts, so Save only lasted one visit)"
assert "Find free care near you" in page_text()

# Home: ZIP field is generic (not NC-only), Medical is the default care type
assert any(ti.label == "Where are you? (ZIP code)" for ti in at.text_input)
assert at.text_input[0].value == "27601"
medical = [b for b in at.button if b.label.startswith("Medical")][0]
assert medical.proto.type == "primary", "Medical should be selected by default"
assert any("When do you need care" in sc.label for sc in at.segmented_control)
assert any("Insurance status" in sb.label for sb in at.selectbox)

print("=== Find ===")
click("Find")
assert "Find care" in page_text()
assert any("Set your search above" in i.value for i in at.info)

print("=== Help ===")
click("Help")
assert "Get help now" in page_text()
assert "tel:911" in page_text() and "tel:988" in page_text()

print("=== About ===")
click("About")
about = [sc for sc in at.segmented_control if "Mission" in sc.options][0]
for section in ["Mission", "Scoring", "Sources", "Privacy"]:
    about.set_value(section).run(timeout=20)
    assert not at.exception, f"About > {section} raised: {at.exception}"
    about = [sc for sc in at.segmented_control if "Mission" in sc.options][0]
assert "Download info" in page_text(), "Privacy should explain Download info, not saving"

print("=== Home again ===")
click("Home")
assert "Find free care near you" in page_text()

print("\n=== ALL NAVIGATION CHECKS PASSED ===")
