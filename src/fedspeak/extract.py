"""Meeting dates from filenames and text from PDFs."""

import re

import pandas as pd
import pdfplumber


def extract_date_from_filename(filename):
    patterns = [
        r'(\d{4})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            y, m, d = match.groups()
            return pd.Timestamp(f"{y}-{m}-{d}")
    return None


def extract_text_from_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text
