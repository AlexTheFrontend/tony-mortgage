# Tony's View tracker - design (part 1)

Date: 2026-10-08
Status: draft, waiting for review

## 1. Goal

Build a private web page that shows, on one timeline from 7 April 2022 to
8 October 2026:

1. The borrower advice in each weekly "Tony's View" issue (the section "If I
   were a borrower, what would I do?").
2. The tone of each issue about the New Zealand economy (ups and downs).
3. The Official Cash Rate (OCR) at each date, with each cut and each increase.
4. Fixed mortgage rates for 1, 2 and 3 years.
5. Extras: the 1-year and 3-year swap rates, and a "Was his advice good?"
   score.

The page is for the owner only. It runs from a local file now. The owner
will deploy it to Vercel later.

## 2. Scope

### In scope (part 1)

- All Tony's View issues from 7 April 2022 to 8 October 2026 (226 issue
  dates after duplicates are removed).
- Not included: "Tview Premium" PDFs. They are Tony's paid newsletter, and
  some of them are in the public media list.
- One record for each issue, made by Claude Code helper agents.
- One static page in `site/` that opens with no server and no internet.

### Out of scope (part 2, a later spec)

- The weekly automatic update for new issues.
- Weekly rates for each lender from the bank web pages.
- Deployment to Vercel, and protection of the Vercel site.
- Tony's monthly Spending Plans Survey.

## 3. Decisions

| Topic | Decision |
|---|---|
| Who sees the page | Only the owner. |
| Where it runs | A local HTML file now. Vercel later. |
| Tony's quotes | Shown in the local build. A build setting removes all quotes. The owner chooses before deployment. |
| How the issues are read | Claude Code helper agents (Sonnet model), with one rule sheet. No Anthropic API key. |
| Extras | Swap rates 1y and 3y. "Was his advice good?" score. |
| Layout | Stacked charts on one shared timeline (layout A). |
| Reserve Bank data | The owner downloads two files in a browser, because the Reserve Bank site blocks scripts (HTTP 403). |
| Swap rates | From the Reserve Bank B2 file, not from Tony's text. B2 is official and has a value for each business day. |

## 4. Data sources

| Chart line | Source | Frequency |
|---|---|---|
| Borrower advice | Tony's View PDF, borrower section, read by an agent | Weekly |
| Economy tone | Tony's View PDF, full issue, read by an agent | Weekly |
| OCR level and changes | Reserve Bank file `hb2-daily-close.xlsx` (series B2, column "OCR") | Daily, changes at each decision |
| Mortgage rates 1y, 2y, 3y | Reserve Bank file `hb20.xlsx` (series B20) | Monthly |
| Lowest lender rates | Tony's View PDF, in the issues where Tony gives his table | Some weeks |
| Swap rates 1y, 3y | Reserve Bank file `hb2-daily-close.xlsx` (series B2, "Swap rates close") | Daily |

Download sources:

- Issue list: `https://www.tonyalexander.nz/wp-json/wp/v2/media?mime_type=application/pdf`
  (380 PDFs in total. After duplicates are removed, 226 Tony's View issue
  dates, 7 April 2022 to 8 October 2026.)
- OCR: `https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx`
- Mortgage rates: `https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b20/hb20.xlsx`

The owner saves the two Reserve Bank files in `data/raw/rbnz/`.

### Known limits

1. **No free weekly rates for each lender.** interest.co.nz has this history,
   but its terms forbid automated copying without a licence. Series B20 is the
   monthly average of the advertised ("carded") rates of all banks. It is not
   the cheapest rate, and it does not include special offers. Special rates
   are usually lower.
2. **Tony's lowest-lender table is not in every issue.** It is in the April
   2022 issue and not in the October 2026 issue. The page shows these points
   only where they exist.
3. **The tone score is a judgement by an AI.** Each score has a reason and a
   quote, so the owner can check it.

## 5. How the data is made

1. `scripts/fetch_issues.py` reads the issue list and downloads each Tony's
   View PDF that is not yet in `data/raw/pdf/`.
2. `scripts/extract_text.py` writes the text of each PDF to `data/raw/text/`.
3. Helper agents read the text files. Each agent gets about 25 issues and the
   rule sheet `rules/extraction-rules.md`. Each agent writes one record for
   each issue to `data/records/YYYY-MM-DD.json`.
4. `scripts/validate.py` checks every record (see section 11). The agents fix
   rejected records. Then the main session hand-checks 10 random records
   against the PDFs.
5. `scripts/build_data.py` combines the records and the two Reserve Bank files
   into `site/data.js`. The option `--no-quotes` removes all quotes.

### Issue dates and duplicates

- The issue date comes from the date printed at the top of the PDF, for
  example "Thursday 7 April 2022", or from the file name. If the two dates
  are the same, use that date. If the PDF has no date, use the file name.
  If the two dates differ, use the date that is closer to the upload date,
  and print a warning. (A typo in the year is easy to make in January.)
- Some issues have two PDFs, for example `Tonys-View-2-July-2026-1.pdf`. Keep
  one issue for each date: the latest upload.

## 6. Record for one issue

```json
{
  "date": "2024-06-13",
  "pdf_url": "https://www.tonyalexander.nz/wp-content/uploads/Tonys-View-13-June-2024.pdf",
  "headline": "Retailing outlook gets worse",
  "borrower": {
    "group": "mix",
    "terms_months": [6, 12],
    "quote": "I would take a mix of 6 and 12 month fixed rates"
  },
  "tone": {
    "score": -2,
    "reason": "Spending plans and the housing market keep getting weaker.",
    "quote": "the results continue to paint a bad and deteriorating picture"
  },
  "lender_min_rates": null,
  "notes": ""
}
```

Field rules:

- `borrower.group` must be one of: `float`, `6m`, `1y`, `18m`, `2y`, `3y_plus`,
  `mix`, `none`.
- `borrower.terms_months` lists every term that Tony names in the advice, in
  months. Permitted values: 0 (a floating part), 6, 12, 18, 24, 36, 48, 60.
  It is empty for `float` and `none`.
- `tone.score` must be an integer from -2 to +2.
- `lender_min_rates` is `null`, or an object from term in months to rate,
  for example `{"24": 6.19, "36": 6.25}`.
- Every `quote` must be text that is in the issue, word for word. Whitespace
  and line breaks can differ.

## 7. Rule sheet for the agents (summary)

The full rule sheet is `rules/extraction-rules.md`. It contains these rules.

### Borrower advice group

| Group | Use when |
|---|---|
| `float` | Tony says he would stay on a floating rate. |
| `6m`, `1y`, `18m`, `2y` | Tony names one term as his choice. |
| `3y_plus` | Tony names 3 years or longer as his choice. |
| `mix` | Tony says he would split the loan across two or more terms. |
| `none` | The issue has no borrower section, or the section gives no advice. |

- If Tony names one choice and an alternative, for example "1 year, or
  perhaps 18 months", the group is the first term. Put both terms in
  `terms_months`.
- Use only what Tony says in that issue. Do not carry advice from an earlier
  issue.

### Economy tone score

The score describes the outlook for the New Zealand economy as Tony
describes it in that issue. It does not describe world markets.

| Score | Meaning |
|---|---|
| -2 | Recession, a sharp fall, or a very bad outlook. |
| -1 | Weak or getting weaker. Mostly negative. |
| 0 | Mixed or flat. |
| +1 | Getting better. Mostly positive. |
| +2 | Strong growth or a clear boom. |

## 8. "Was his advice good?" score

1. Use a sample loan of $500,000. The page lets the owner change it.
2. The loan is interest-only, so the balance does not change. Break fees are
   not included.
3. **Tony's strategy:** start on 7 April 2022 with the advice in that issue.
   When a fixed part of the loan ends, split it evenly across the terms in
   Tony's latest advice, and fix each piece at the B20 rate for that term in
   that month. `3y_plus` uses the 3-year rate. `float` uses the B20 floating
   rate. If the latest advice is `none`, use the last advice that was not
   `none`. If no advice exists yet, use the 1-year rate.
4. A floating part has no end date. Check it each month: if the latest
   advice is not `float`, fix that part by the rule in step 3.
5. **Compare with:** "always fix for 1 year" and "always float".
6. Calculate monthly to the last month in the B20 file.
7. Show the total interest of each strategy over time.

Details:

- The "latest advice" for a month is the advice in the last issue published
  in or before that month.
- A term longer than 3 years is fixed for 3 years at the 3-year rate.
- If B20 has no 18-month rate for a month, use the mean of the 1-year and
  2-year rates for that month. If another rate is missing, stop with an
  error.
- A floating part inside a mix (term 0) follows the floating rate.

B20 rates are averages of advertised rates. The result shows which strategy
did better, not the exact dollar amount that a borrower paid.

## 9. The page

One page, `site/index.html`, with stacked charts on one shared timeline.

1. **Summary row:** the current OCR, Tony's latest advice, his latest tone,
   and the result of the advice score.
2. **Rates chart:** the OCR as a step line, with a marker at each change (for
   example "▲ +0.75" and "▼ -0.50"). The B20 rates for 1, 2 and 3 years. The
   swap rates as dotted lines. Tony's lowest lender rates as points.
3. **Advice strip:** one coloured cell for each week. The colour shows the
   group. A mix has its own colour, and its label lists the terms.
4. **Tone chart:** one bar for each week from -2 to +2, plus an 8-week
   average line.
5. **Advice score chart:** the total interest of each strategy over time.
6. **Range slider:** zoom in on part of the timeline.

Interaction:

- Hover on a week to show a vertical line through all charts, and a tooltip
  with all values for that week.
- Click a week to open a details panel: headline, borrower quote, tone reason
  and quote, and a link to the PDF.

Technical:

- Apache ECharts (an exact version, saved in `site/vendor/`), so the page
  works offline.
- The data is in `site/data.js` (not JSON), so the page works from `file://`.
- Light and dark mode.

## 10. Folder layout

```
data/raw/pdf/      Tony's View PDFs              (local only, never deployed)
data/raw/text/     text of each PDF              (local only, never deployed)
data/raw/rbnz/     hb2-daily-close.xlsx, hb20.xlsx     (owner downloads)
data/records/      one JSON record per issue
rules/             extraction-rules.md
scripts/           fetch, extract, validate, build (Python)
tests/             pytest tests for the scripts
site/              index.html, app.js, style.css, data.js, vendor/   (deployed later)
docs/              this spec and the plan
```

Python dependencies are managed with `uv`: `pypdf`, `openpyxl`, `pytest`.

## 11. Checks and tests

### Script tests (pytest, written before the code)

- Read the issue list, and get dates from file names (including `-1`
  duplicates).
- Get the issue date from the PDF header text.
- Validate records: good records pass, and each kind of bad record fails.
- Read the OCR, swap and B20 values from the Reserve Bank files, and find the
  OCR changes.
- The advice score on a small example that is calculated by hand.
- `--no-quotes` removes every quote from the output.

### Record checks (`validate.py`)

1. The record date matches the issue date.
2. `group` and `score` have permitted values.
3. Each quote is in the issue text.
4. Each issue has exactly one record.

### Hand check

The main session checks 10 random records against the PDFs. At least 9 of 10
must have the correct advice group and a tone score that the main session
agrees with, within 1 point. If fewer pass, fix the rule sheet and run the
agents again.

### Page check

Open `site/index.html` in a browser. Check hover, click, the slider, light
and dark mode, and that the console has no errors.

## 12. Success criteria

1. Every Tony's View issue from 7 April 2022 to 8 October 2026 has a valid
   record.
2. The OCR line matches the Reserve Bank file at every change.
3. The hand check passes (at least 9 of 10).
4. `site/index.html` opens from the file system with no internet and shows
   all charts in section 9.
5. `build_data.py --no-quotes` makes a page with no text from Tony's issues
   other than headlines.

## 13. Open items

1. The owner downloads `hb2-daily-close.xlsx` and `hb20.xlsx` before the build
   step.
2. The owner decides about quotes on Vercel before part 2.
3. Part 2 must check the terms of use of each bank before a script reads its
   rates page.
