"""HTML minutes extraction. Each case reproduces a problem found in the real archive."""

from fedspeak.extract import extract_text_from_html


def write(tmp_path, html, encoding="utf-8"):
    path = tmp_path / "page.htm"
    path.write_bytes(html.encode(encoding))
    return path


def test_modern_page_uses_article_block_only(tmp_path):
    html = """<html><head><title>FOMC</title></head><body>
      <div class="t1_nav">Home Monetary Policy News</div>
      <div id="article"><p>Minutes of the Federal Open Market Committee.</p>
        <p>Inflation remained elevated.</p></div>
      <div id="footer">Last update: February 22, 2023</div></body></html>"""
    assert extract_text_from_html(write(tmp_path, html)) == \
        "Minutes of the Federal Open Market Committee. Inflation remained elevated."


def test_1990s_return_to_top_between_sections_keeps_later_sections(tmp_path):
    # 1996-11-13 lost 90 percent of its text when everything after the first
    # "[Return to top]" was treated as footer.
    html = """<HTML><HEAD><TITLE>FRB: FOMC Minutes</TITLE></HEAD><body>
      <P>Section one on the economic outlook.</P><A HREF="#top">[Return to top]</A>
      <P>Section two noted that inflation was subdued.</P><A HREF="#top">[Return to top]</A>
      <P>Donald L. Kohn Secretary</P>
      <A HREF="/">Home</A> | <A HREF="/fomc/">FOMC</A> Accessibility. Last update: July 16, 1996
      </body></HTML>"""
    text = extract_text_from_html(write(tmp_path, html))
    assert "Section two noted that inflation was subdued." in text
    assert text.endswith("Donald L. Kohn Secretary")
    assert "Return to top" not in text


def test_footer_with_lowercase_policy_is_removed(tmp_path):
    html = """<html><body><div id="content"><p>The meeting adjourned. Secretary</p>
      <p>FOMC Home | Monetary policy Accessibility | Contact Us</p></div></body></html>"""
    assert extract_text_from_html(write(tmp_path, html)) == "The meeting adjourned. Secretary"


def test_footnote_back_links_removed_with_nonbreaking_spaces(tmp_path):
    html = """<html><body><div id="article"><p>1. Attended Tuesday's session only.
      <a href="#f1">Return&nbsp;to&nbsp;text</a></p></div></body></html>"""
    assert extract_text_from_html(write(tmp_path, html)) == "1. Attended Tuesday's session only."


def test_replacement_character_from_source_restored_or_spaced(tmp_path):
    # Several 1999 to 2007 pages contain U+FFFD in the Fed's own file.
    html = "<html><body><p>the System�s account; an increase of � percentage point</p></body></html>"
    text = extract_text_from_html(write(tmp_path, html))
    assert "System's account" in text
    assert "�" not in text
    assert "of percentage point" in text


def test_invisible_characters_do_not_split_words(tmp_path):
    # Soft hyphens appear inside words in 2016 to 2024 pages ("al\xadthough").
    html = ("<html><body><div id='article'><p>al­though infla­tion and longer‑run "
            "May 2‍–‍3</p></div></body></html>")
    text = extract_text_from_html(write(tmp_path, html))
    assert text == "although inflation and longer-run May 2–3"


def test_page_encoding_is_detected(tmp_path):
    html = ('<html><head><meta charset="windows-1252"></head><body><div id="article">'
            "<p>January 31–February 1, 2023: the Committee’s view</p></div></body></html>")
    text = extract_text_from_html(write(tmp_path, html, encoding="cp1252"))
    assert text == "January 31–February 1, 2023: the Committee’s view"
