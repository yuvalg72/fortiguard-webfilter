from pathlib import Path

import webfilter


def test_parse_category_heading_with_link():
    html = '<html><h4>Category: <a href="#">Information Technology</a></h4></html>'
    assert webfilter.parse_category(html) == "Information Technology"


def test_parse_category_heading_plain_text():
    html = '<html><h3>Category: Artificial Intelligence Technology</h3></html>'
    assert webfilter.parse_category(html) == "Artificial Intelligence Technology"


def test_parse_category_info_title():
    html = '<html><div class="info_title">Category: Finance and Banking</div></html>'
    assert webfilter.parse_category(html) == "Finance and Banking"


def test_parse_category_search_phrase():
    html = '<html><body>The address has been found as Business</body></html>'
    assert webfilter.parse_category(html) == "Business"


def test_parse_category_returns_none_when_missing():
    assert webfilter.parse_category("<html><body>No rating here</body></html>") is None


def test_read_targets_ignores_comments_blanks_and_duplicates(tmp_path: Path):
    input_file = tmp_path / "targets.txt"
    input_file.write_text(
        "# comment\n\nexample.com\nhttps://openai.com/path\nexample.com\n",
        encoding="utf-8",
    )

    assert webfilter.read_targets(input_file) == [
        "example.com",
        "https://openai.com/path",
    ]
