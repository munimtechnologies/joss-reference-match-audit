# joss-reference-match-audit

When Crossref matches a reference in a journal's deposit to a DOI by itself, the link is marked
`"doi-asserted-by": "crossref"`, and the matched work gets a citation. Papers in the Journal of
Open Source Software (JOSS) often cite software by name and URL only. This repository checks,
for every JOSS paper in Crossref, whether those automatic links point to the work that was
actually cited.

## Result of audit 1 (graded 2026-11-07)

6 of 9 pre-registered predictions held. See [GRADING-1.md](GRADING-1.md).

- 3,787 JOSS papers; 54,574 references; 1,144 reference DOIs were added by Crossref's matcher.
- **At least 14 of those links are hand-confirmed wrong**, for example corner.py ->
  "Cookery corner" (*Nursery World*), the R package broom -> the book *Bromance*, cvui (a UI
  library) -> a solar-cell paper, and Jupyter -> a sports-science paper.
- **Software references are the weak spot:** 7 of the 59 matched references to a code host
  (GitHub, Bitbucket, CRAN, ...) are confirmed wrong, against 5 confirmed among the flagged
  links in the other 1,083.
- No suspect link appears in deposits made after Crossref changed its matching on 2026-01-29
  (0 of 1,678 references; about 4.4 expected at the old rate).
- 24 matched links in 22 papers point a JOSS paper at itself (a reference to its own software).
- Negative results: the automatic suspect test was noisy (12 of 34 flags were real errors; most
  false alarms were URL-encoded or MathML-marked text), and the flag rate among
  publisher-supplied DOIs (3.5%) was no lower than among Crossref's matches (3.0%). Outside
  software references, Crossref's matches look about as reliable as the publisher's DOIs.

| JOSS paper | Reference text | Crossref linked it to |
|---|---|---|
| 10.21105/joss.00024 | "corner.py on GitHub, 2016, https://github.com/dfm/corner.py" | 10.12968/nuwa.2016.25.26, "Cookery corner", *Nursery World* |
| 10.21105/joss.00236 | "Mutel, Christopher, brightway2-data, 2016" | 10.9790/1959-0504040105, a 2016 nursing paper whose first author is named Christopher |
| 10.21105/joss.05466 | "broom: Convert statistical objects into tidy tibbles" (CRAN) | 10.1007/978-3-030-98610-0, *Bromance* |

## Files

- `PREREG.md`: question, prior work, fixed method and nine predictions, written before the
  audit ran.
- `GRADING-1.md`: the graded first run, with every hand grade explained.
- `results/refmatch1/`: `summary.json`, `suspects.csv`, `suspect_search_check.csv`, the hand
  grades (`hand_grades_suspects.csv`, `hand_grades_plausible.csv`) and, where size allows,
  `crossref_asserted.csv` (all 1,144 matched links, scored) and `publisher_sample.csv`.
- `ref_match_audit.py`: the audit (Python 3.12, standard library only, no API keys). Reads
  `api.crossref.org` and `doi.org` at a polite pace.
- `test_ref_match_audit.py`: unit tests (`python -m unittest -v`).

Run: `python ref_match_audit.py --out-dir out`

A "suspect" row is a lead for a person to check, not a finding. Only hand-confirmed links are
reported as wrong.

Related: [joss-cff-census](https://github.com/munimtechnologies/joss-cff-census) (the
CITATION.cff files of JOSS repositories) and
[joss-archive-doi-audit](https://github.com/munimtechnologies/joss-archive-doi-audit) (the
software archive DOI of every JOSS paper).

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed the results. Code Apache-2.0; text and data CC BY 4.0.
