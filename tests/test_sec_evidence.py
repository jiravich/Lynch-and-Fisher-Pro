from sec_evidence import build_evidence_candidates, html_to_text


def test_html_to_text_removes_scripts_and_normalizes():
    html = "<html><script>ignore me</script><body><h1>Item 1. Business</h1><p>Company sells products globally.</p></body></html>"
    text = html_to_text(html)
    assert "ignore me" not in text
    assert "Company sells products globally." in text


def test_build_evidence_candidates_uses_only_source_text():
    text = (
        "The company increased revenue growth by 20 percent in the latest year. "
        "The market opportunity remains large and demand continues to expand. "
        "The company faces intense competition from several competitors. "
        "Research and development spending supports new product development."
    )
    candidates = build_evidence_candidates(text, limit_per_topic=1)

    statements = {item["statement"] for item in candidates}
    assert any("revenue growth" in item.lower() for item in statements)
    assert any("market opportunity" in item.lower() for item in statements)
    assert all(item["fact_or_inference"] == "Fact" for item in candidates)
    assert all(len(item["statement"]) <= 500 for item in candidates)


def test_build_evidence_candidates_has_no_candidates_from_unrelated_text():
    candidates = build_evidence_candidates(
        "A simple sentence about something unrelated to the research framework."
    )
    assert candidates == []
