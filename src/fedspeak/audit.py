"""Human audit of keyword hits (plan 1.5).

build_audit draws a fixed random sample of hits per keyword and writes:
- output/audit/audit.html         a page for a reader to mark each hit: is it a real
                                  mention of the topic, and what is the tone toward it
- output/audit/audit_sample.csv   the sample, with every context variant's score

Scores are hidden on the page until the reader chooses to reveal them, so they do not
influence the labels. Labels are kept in the browser and downloaded as a CSV.

score_audit compares downloaded labels with each context variant's score.
"""

import html
import json
import random
from pathlib import Path

import pandas as pd

from fedspeak.config import KEYWORDS, MANIFEST_CSV, PROJECT_ROOT, TEXT_DIR
from fedspeak.match import find_hits
from fedspeak.sentiment import score_hits
from fedspeak.verify import CONTEXT_VARIANTS, _tone

AUDIT_DIR = PROJECT_ROOT / "output" / "audit"
AUDIT_SEED = 2026
AUDIT_PER_KEYWORD = 30


def draw_sample(keywords=KEYWORDS, per_keyword=AUDIT_PER_KEYWORD, seed=AUDIT_SEED, text_dir=TEXT_DIR):
    """Random hits per keyword across the whole corpus, scored under every context variant."""
    texts, pool = {}, {kw: [] for kw in keywords}
    for path in sorted(Path(text_dir).glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        texts[path.name] = text
        for hit in find_hits(text, keywords):
            pool[hit.keyword].append((path.name, hit))

    rng = random.Random(seed)
    manifest = pd.read_csv(MANIFEST_CSV, dtype=str).fillna("") if Path(MANIFEST_CSV).exists() else None
    urls = dict(zip(manifest.meeting_date.str.replace("-", ""), manifest.html_url)) if manifest is not None else {}

    rows = []
    for kw in keywords:
        chosen = rng.sample(pool[kw], min(per_keyword, len(pool[kw])))
        for name, hit in sorted(chosen, key=lambda x: (x[0], x[1].start)):
            text = texts[name]
            date = name[len("fomcminutes"):-len(".txt")]
            row = {
                "id": f"{date}-{kw.replace(' ', '_')}-{hit.start}",
                "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                "keyword": kw,
                "matched": hit.matched,
                "char_start": hit.start,
                "word_start": hit.word_start,
                "word_end": hit.word_end,
                "source_url": urls.get(date, ""),
            }
            for vname, params in CONTEXT_VARIANTS.items():
                (rec,) = score_hits(text, [hit], **params)
                row[f"{vname}_score"] = rec["score"]
                row[f"{vname}_start"] = hit.word_start - rec["words_left"]
                row[f"{vname}_end"] = hit.word_end + rec["words_right"] + 1
            rows.append((row, text.split()))
    return rows


def _render_tokens(words, start, end, hit_start, hit_end, inner=None):
    out = []
    for i in range(start, end):
        token = html.escape(words[i])
        if hit_start <= i <= hit_end:
            token = f"<mark>{token}</mark>"
        if inner and inner[0] <= i < inner[1]:
            token = f"<b>{token}</b>"
        out.append(token)
    return " ".join(out)


def build_audit(keywords=KEYWORDS, per_keyword=AUDIT_PER_KEYWORD, seed=AUDIT_SEED, out_dir=AUDIT_DIR,
                text_dir=TEXT_DIR):
    rows = draw_sample(keywords, per_keyword, seed, text_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([r for r, _ in rows]).to_csv(out_dir / "audit_sample.csv", index=False)

    items = []
    for n, (r, words) in enumerate(rows, 1):
        sentence = _render_tokens(words, r["sentence_start"], r["sentence_end"], r["word_start"], r["word_end"])
        window = _render_tokens(words, r["window75_start"], r["window75_end"], r["word_start"], r["word_end"],
                                inner=(r["sentence_start"], r["sentence_end"]))
        scores = " &middot; ".join(
            f"{v}: {r[f'{v}_score']:+.3f} ({_tone(r[f'{v}_score'])})" for v in CONTEXT_VARIANTS)
        link = (f'<a href="{html.escape(r["source_url"])}" target="_blank" rel="noopener">source</a>'
                if r["source_url"] else "")
        rid = html.escape(r["id"])
        items.append(f"""
<section class="item" data-id="{rid}" data-keyword="{html.escape(r['keyword'])}">
  <header><span class="num">{n}</span><span class="kw">{html.escape(r['keyword'])}</span>
    <span class="date">{r['date']}</span>{link}</header>
  <p class="sentence">{sentence}</p>
  <details><summary>75-word window (sentence in bold)</summary><p class="window">{window}</p></details>
  <div class="q"><span>Real mention of the topic?</span>
    <label><input type="radio" name="m-{rid}" value="yes">Yes</label>
    <label><input type="radio" name="m-{rid}" value="no">No</label></div>
  <div class="q"><span>Tone toward it in this sentence</span>
    <label><input type="radio" name="t-{rid}" value="negative">Negative</label>
    <label><input type="radio" name="t-{rid}" value="neutral">Neutral</label>
    <label><input type="radio" name="t-{rid}" value="positive">Positive</label></div>
  <input class="note" type="text" placeholder="Note (optional)" data-note="{rid}">
  <p class="scores">{scores}</p>
</section>""")

    page = PAGE.replace("{{ITEMS}}", "\n".join(items)) \
               .replace("{{COUNT}}", str(len(rows))) \
               .replace("{{STORAGE_KEY}}", json.dumps(f"fedspeak-audit-{seed}-{per_keyword}-{'|'.join(keywords)}")) \
               .replace("{{SEED}}", str(seed))
    (out_dir / "audit.html").write_text(page, encoding="utf-8")
    return out_dir / "audit.html", len(rows)


def score_audit(labels_csv, sample_csv=AUDIT_DIR / "audit_sample.csv"):
    """Agreement between a reader's labels and each context variant's tone label."""
    labels = pd.read_csv(labels_csv, dtype=str).fillna("")
    sample = pd.read_csv(sample_csv)
    df = sample.merge(labels.drop(columns=["keyword"], errors="ignore"), on="id", how="inner")
    print(f"Labelled hits: {len(df)} of {len(sample)}")

    m = df[df.match_ok.isin(["yes", "no"])]
    if len(m):
        print(f"\nReal mention of the topic: {(m.match_ok == 'yes').mean():.0%} of {len(m)} hits")
        for kw, g in m.groupby("keyword"):
            print(f"  {kw:<14} {(g.match_ok == 'yes').mean():.0%} ({len(g)})")

    t = df[df.tone.isin(["negative", "neutral", "positive"]) & (df.match_ok != "no")]
    if len(t):
        print(f"\nTone agreement with the reader ({len(t)} hits labelled, real mentions only):")
        for v in CONTEXT_VARIANTS:
            pred = t[f"{v}_score"].map(_tone)
            line = "  ".join(f"{kw} {(pred[t.keyword == kw] == t.tone[t.keyword == kw]).mean():.0%}"
                             for kw in t.keyword.unique())
            print(f"  {v:<14} overall {(pred == t.tone).mean():.0%}   {line}")
        print("\nReader's tone labels:", t.tone.value_counts().to_dict())
    return df


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FedSpeak Audit</title>
<style>
:root { --bg:#fbfbf9; --fg:#1d1d1b; --muted:#6b6b66; --card:#fff; --line:#e3e2dc; --mark:#ffe28a; --accent:#2f5d8a; }
@media (prefers-color-scheme: dark) { :root { --bg:#16171a; --fg:#e7e6e1; --muted:#9a9a94; --card:#1f2024; --line:#33343a; --mark:#6b5310; --accent:#8ab4e0; } }
* { box-sizing:border-box } body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, sans-serif; }
main { max-width:860px; margin:0 auto; padding:24px 16px 80px; }
h1 { font-size:22px; margin:0 0 4px } .intro { color:var(--muted); margin:0 0 16px }
.bar { position:sticky; top:0; background:var(--bg); padding:10px 0; border-bottom:1px solid var(--line); display:flex; gap:12px; flex-wrap:wrap; align-items:center; z-index:1 }
button { font:inherit; padding:6px 12px; border:1px solid var(--line); background:var(--card); color:var(--fg); border-radius:6px; cursor:pointer }
.item { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px 16px; margin:14px 0 }
.item.done { border-left:4px solid var(--accent) }
.item header { display:flex; gap:10px; align-items:baseline; color:var(--muted); font-size:14px }
.num { font-weight:600; color:var(--fg) } .kw { font-weight:600; color:var(--accent) }
.sentence { font-size:17px; margin:8px 0 } .window { color:var(--muted); font-size:14px } .window b { color:var(--fg); font-weight:500 }
mark { background:var(--mark); color:inherit; padding:0 2px; border-radius:3px }
.q { display:flex; flex-wrap:wrap; gap:6px 14px; margin:6px 0; font-size:15px } .q span { min-width:220px; color:var(--muted) }
.note { width:100%; margin-top:6px; padding:6px 8px; font:inherit; font-size:14px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg) }
.scores { display:none; font-size:13px; color:var(--muted); margin:8px 0 0; font-family:ui-monospace, monospace }
body.reveal .scores { display:block }
a { color:var(--accent) }
</style></head><body><main>
<h1>FedSpeak Audit</h1>
<p class="intro">{{COUNT}} keyword hits drawn at random from all FOMC minutes since 1993 (seed {{SEED}}). For each one, mark whether
it really refers to the topic, and the tone toward the topic in the highlighted sentence. Answers are saved in this browser as you go.
Scores stay hidden until you reveal them, so they do not influence your judgment. When done, download the labels and run
<code>uv run fedspeak audit --labels &lt;file&gt;</code>.</p>
<div class="bar"><span id="progress"></span>
  <button id="download">Download labels (CSV)</button>
  <button id="reveal">Reveal scores</button></div>
{{ITEMS}}
</main>
<script>
const KEY = {{STORAGE_KEY}};
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
const items = [...document.querySelectorAll(".item")];
function refresh() {
  let done = 0;
  for (const el of items) {
    const s = state[el.dataset.id] || {};
    const complete = s.match === "no" || (s.match && s.tone);
    el.classList.toggle("done", !!complete); if (complete) done++;
  }
  document.getElementById("progress").textContent = done + " of " + items.length + " labelled";
}
for (const el of items) {
  const id = el.dataset.id, s = state[id] || {};
  for (const input of el.querySelectorAll("input[type=radio]")) {
    const field = input.name.startsWith("m-") ? "match" : "tone";
    if (s[field] === input.value) input.checked = true;
    input.addEventListener("change", () => { state[id] = { ...(state[id] || {}), [field]: input.value }; save(); refresh(); });
  }
  const note = el.querySelector(".note"); note.value = s.note || "";
  note.addEventListener("input", () => { state[id] = { ...(state[id] || {}), note: note.value }; save(); });
}
document.getElementById("reveal").addEventListener("click", (e) => {
  document.body.classList.toggle("reveal");
  e.target.textContent = document.body.classList.contains("reveal") ? "Hide scores" : "Reveal scores";
});
document.getElementById("download").addEventListener("click", () => {
  const q = (v) => '"' + String(v || "").replace(/"/g, '""') + '"';
  const lines = ["id,keyword,match_ok,tone,note"];
  for (const el of items) { const s = state[el.dataset.id] || {}; lines.push([el.dataset.id, el.dataset.keyword, s.match, s.tone, s.note].map(q).join(",")); }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\\n")], { type: "text/csv" }));
  a.download = "fedspeak_audit_labels.csv"; a.click();
});
refresh();
</script></body></html>
"""
