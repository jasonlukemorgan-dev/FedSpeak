"""Parsing of federalreserve.gov pages. Fixtures copy the structure of the real pages; no network."""

from fedspeak.fetch import classify_meeting, parse_calendar_page, parse_historical_page

PAGE = "https://www.federalreserve.gov/monetarypolicy/fomchistorical2020.htm"

HISTORICAL_2020 = """
<div class="panel panel-default">
  <h5 class="panel-heading">January 28-29 Meeting - 2020</h5>
  <p><a href="/monetarypolicy/files/FOMC20200129meeting.pdf">Transcript</a></p>
  <p>Minutes (Released February 19, 2020):<br>
    <a href="/monetarypolicy/fomcminutes20200129.htm">HTML</a> |
    <a href="/monetarypolicy/files/fomcminutes20200129.pdf">PDF</a></p>
</div>
<div class="panel panel-default">
  <h5 class="panel-heading">March 15 (unscheduled) Meeting - 2020</h5>
  <p><a href="/monetarypolicy/files/FOMC20200315Agenda.pdf">Agenda</a></p>
  <p>Minutes (Released April 08, 2020):<br>
    <a href="/monetarypolicy/fomcminutes20200315.htm">HTML</a> |
    <a href="/monetarypolicy/files/fomcminutes20200315.pdf">PDF</a></p>
</div>
"""

HISTORICAL_2008 = """
<div class="panel panel-default">
  <h5 class="panel-heading">June 24-25 Meeting - 2008</h5>
  <p>Minutes (Released Jul 16, 2008):
  <br /><a href="/monetarypolicy/fomc20080625.htm">HTML</a> | <a href="/monetarypolicy/files/fomcminutes20080625.pdf">310 KB PDF</a></p>
</div>
"""

HISTORICAL_1993 = """
<div class="panel panel-default">
  <h5 class="panel-heading">February 2-3 Meeting - 1993</h5>
  <p><a href="/fomc/MINUTES/1993/19930203min.htm">Minutes</a> (Released March 26, 1993)</p>
</div>
<div class="panel panel-default">
  <h5 class="panel-heading">February 18 Conference Call - 1993</h5>
  <p>No minutes link here.</p>
</div>
"""

HISTORICAL_2007 = """
<div class="panel panel-default">
  <h5 class="panel-heading">August 7 Meeting - 2007</h5>
  <p><a href="/fomc/minutes/20070807.htm">Minutes</a> (Released Aug 28, 2007)</p>
</div>
<div class="panel panel-default">
  <h5 class="panel-heading">August 10 Conference Call - 2007</h5>
  <p><a href="/fomc/minutes/20070918.htm#august10">Minutes</a> (Released Oct 9, 2007)</p>
</div>
"""

HISTORICAL_2012 = """
<div class="panel panel-default">
  <h5 class="panel-heading">October 23-24 Meeting - 2012</h5>
  <p>Minutes (Released November 14, 2012):<br>
    <a href="/monetarypolicy/fomcminutes20121024.htm">HTML</a> |
    <a href="/monetarypolicy/files/fomcminutes20121023.pdf">PDF</a></p>
</div>
"""

CALENDAR = """
<div class="panel panel-default"><div class="panel-heading"><h4>2023 FOMC Meetings</h4></div>
  <div class="row fomc-meeting">
    <div class="fomc-meeting__month"><strong>Jan/Feb</strong></div>
    <div class="fomc-meeting__date">31-1</div>
    <div class="fomc-meeting__minutes"><strong>Minutes:</strong><br>
      <a href="/monetarypolicy/files/fomcminutes20230201.pdf">PDF</a> | <a href="/monetarypolicy/fomcminutes20230201.htm">HTML</a>
      <br> (Released February 22, 2023)</div>
  </div>
  <div class="row fomc-meeting">
    <div class="fomc-meeting__month"><strong>Mar</strong></div>
    <div class="fomc-meeting__date">21-22*</div>
    <div class="fomc-meeting__minutes"><strong>Minutes:</strong><br></div>
  </div>
</div>
<div class="panel panel-default"><div class="panel-heading"><h4>2024 FOMC Meetings</h4></div></div>
"""


def by_date(records):
    return {r.meeting_date: r for r in records}


def test_historical_page_pairs_html_and_pdf_with_release_date():
    recs = by_date(parse_historical_page(HISTORICAL_2020, PAGE))
    assert set(recs) == {"2020-01-29", "2020-03-15"}
    jan = recs["2020-01-29"]
    assert jan.html_url == "https://www.federalreserve.gov/monetarypolicy/fomcminutes20200129.htm"
    assert jan.pdf_url == "https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20200129.pdf"
    assert jan.release_date == "2020-02-19"
    assert jan.meeting_type == "scheduled"


def test_unscheduled_meeting_is_tagged():
    rec = by_date(parse_historical_page(HISTORICAL_2020, PAGE))["2020-03-15"]
    assert rec.meeting_type == "unscheduled"
    assert rec.meeting_label == "March 15 (unscheduled) Meeting - 2020"


def test_transcripts_and_agendas_are_not_treated_as_minutes():
    urls = [u for r in parse_historical_page(HISTORICAL_2020, PAGE) for u in (r.html_url, r.pdf_url)]
    assert not any("meeting.pdf" in u or "Agenda" in u for u in urls)


def test_2008_style_html_url_and_short_month_release_date():
    rec = by_date(parse_historical_page(HISTORICAL_2008, PAGE))["2008-06-25"]
    assert rec.html_url.endswith("/monetarypolicy/fomc20080625.htm")
    assert rec.release_date == "2008-07-16"


def test_1990s_html_only_minutes():
    recs = by_date(parse_historical_page(HISTORICAL_1993, PAGE))
    assert set(recs) == {"1993-02-03"}
    assert recs["1993-02-03"].html_url.endswith("/fomc/MINUTES/1993/19930203min.htm")
    assert recs["1993-02-03"].pdf_url == ""
    assert recs["1993-02-03"].release_date == "1993-03-26"


def test_1996_to_2007_url_format_and_fragment_links_skipped():
    recs = by_date(parse_historical_page(HISTORICAL_2007, PAGE))
    assert set(recs) == {"2007-08-07"}  # the #august10 link points into September's minutes
    assert recs["2007-08-07"].html_url.endswith("/fomc/minutes/20070807.htm")
    assert recs["2007-08-07"].release_date == "2007-08-28"


def test_mismatched_html_and_pdf_dates_stay_one_meeting():
    recs = parse_historical_page(HISTORICAL_2012, PAGE)
    assert len(recs) == 1
    assert recs[0].meeting_date == "2012-10-24"
    assert recs[0].pdf_url.endswith("fomcminutes20121023.pdf")
    assert recs[0].html_url.endswith("fomcminutes20121024.htm")


def test_calendar_page_reads_years_and_skips_unreleased_minutes():
    recs, years = parse_calendar_page(CALENDAR, "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    assert years == [2023, 2024]
    recs = by_date(recs)
    assert set(recs) == {"2023-02-01"}
    assert recs["2023-02-01"].release_date == "2023-02-22"
    assert recs["2023-02-01"].meeting_label == "Jan/Feb 31-1 Meeting - 2023"


def test_classify_meeting():
    assert classify_meeting("March 15 (unscheduled) Meeting - 2020") == "unscheduled"
    assert classify_meeting("October 5 Conference Call - 1993") == "conference_call"
    assert classify_meeting("March 19 (notation vote) - 2020") == "notation_vote"
    assert classify_meeting("June 24-25 Meeting - 2008") == "scheduled"
