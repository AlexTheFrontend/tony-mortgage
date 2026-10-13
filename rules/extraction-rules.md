# Rule sheet: one record for one Tony's View issue

You read the text of one weekly "Tony's View" issue by Tony Alexander and write
one JSON record. Use only the text of that issue. Do not use your own knowledge
of the economy, and do not use other issues.

## Input

- `data/raw/text/<date>.txt` - the text of the issue. It comes from a PDF, so
  lines and even words can break in odd places ("an d").
- `data/raw/issues.json` - the `pdf_url` for each date.

## Output

Write `data/records/<date>.json` with exactly these fields:

```json
{
  "date": "2024-06-13",
  "pdf_url": "https://www.tonyalexander.nz/wp-content/uploads/Tonys-View-13-June-2024.pdf",
  "headline": "Retailing outlook gets worse",
  "borrower": {
    "group": "mix",
    "terms_months": [6, 12],
    "quote": "If I were borrowing at the moment, I would take a mix of 6 and 12 month fixed rates"
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

## Fields

### date, pdf_url

Copy them from `data/raw/issues.json`.

### headline

The title of the first article, word for word. It is the first line of text
after "Sign up for free at www.tonyalexander.nz".

### borrower

1. Find the section "If I were a borrower, what would I do?". It is usually in
   the second half of the issue.
2. Read the whole section. Most of it is commentary about interest rates. The
   advice is usually one or two sentences, for example "If I were borrowing at
   the moment, I would fix for one year."
3. Choose the group:

| group | Use when Tony says he would ... |
|---|---|
| `float` | stay on a floating rate |
| `6m` | fix for 6 months |
| `1y` | fix for 1 year (12 months) |
| `18m` | fix for 18 months |
| `2y` | fix for 2 years |
| `3y_plus` | fix for 3 years or longer |
| `mix` | split the loan across two or more terms |
| `none` | (the issue has no borrower section, or the section gives no advice) |

4. `terms_months`: every term that Tony names in the advice, in months, in the
   order he names them. Permitted values: 0 (a floating part), 6, 12, 18, 24,
   36, 48, 60. Use `[]` for `float` and `none`.
5. `quote`: the advice sentence, word for word, at most 300 characters. You can
   join words that are broken across lines. Use `""` for `none`.

Rules for hard cases:

- One choice with an alternative ("one year, or perhaps 18 months"): the group
  is the first term. `terms_months` lists both: `[12, 18]`.
- A split ("a mix of 6 and 12 month fixed rates", "spread across 1, 2 and 3
  years"): `mix`, with all terms: `[6, 12]`.
- Part floating, part fixed: `mix`, with 0 for the floating part: `[0, 12]`.
- Terms in words: "six months" = 6, "one year" = 12, "eighteen months" = 18,
  "two years" = 24, "three years" = 36.
- "My view is unchanged" without a term: `none`, and write
  "advice unchanged, term not stated" in `notes`.
- Do not copy advice from an earlier issue.

### tone

Read the whole issue. Score Tony's overall view of the New Zealand economy:
where it is now and where it goes in the next few months. Do not score world
markets.

| score | Meaning |
|---|---|
| -2 | Recession, a sharp fall, or a very bad outlook |
| -1 | Weak or getting weaker; mostly negative |
| 0 | Mixed or flat |
| +1 | Getting better; mostly positive |
| +2 | Strong growth or a clear boom |

- `score`: an integer (`-2`, `-1`, `0`, `1`, `2`), not a string.
- `reason`: one sentence in your own words, at most 20 words.
- `quote`: one sentence from the issue, word for word, that best supports the
  score.

### lender_min_rates

Only when the issue has Tony's table or list of the current lowest (minimum)
fixed mortgage rates that lenders charge. Record the term in months (as a
string key) and the rate (as a number), for example `{"24": 6.19, "36": 6.25}`.
Do not record forecasts, averages, swap rates, or one bank's rate that he
mentions in passing. In all other issues: `null`.

### notes

`""`, or one short sentence about something unusual, for example "No borrower
section this week".

## Check your work

Run:

```bash
uv run python -m scripts.validate --dates <your dates, comma-separated>
```

Fix every problem it reports, then run it again until it prints
`all records valid`. The most common problem is a quote that is not word for
word. Copy the quote from the text file again.
