# joss-reference-match-audit

When Crossref matches a reference in a journal's deposit to a DOI by itself, the link is marked
`"doi-asserted-by": "crossref"`, and the matched work gets a citation. Papers in the Journal of
Open Source Software (JOSS) often cite software by name and URL only. This repository checks,
for every JOSS paper in Crossref, whether those automatic links point to the work that was
actually cited.

Two links that started this study:

| JOSS paper | Reference text | Crossref linked it to |
|---|---|---|
| 10.21105/joss.00024 | "corner.py on GitHub, 2016, https://github.com/dfm/corner.py" | 10.12968/nuwa.2016.25.26, "Cookery corner", *Nursery World* |
| 10.21105/joss.00236 | "Mutel, Christopher, brightway2-data, 2016" | 10.9790/1959-0504040105, a 2016 nursing paper whose first author is named Christopher |

- `PREREG.md`: question, prior work, fixed method and nine predictions, written before the
  audit ran.
- `ref_match_audit.py`: the audit (Python 3.12, standard library only, no API keys). Reads
  `api.crossref.org` and `doi.org` at a polite pace.
- `test_ref_match_audit.py`: unit tests (`python -m unittest -v`).

Run: `python ref_match_audit.py --out-dir out`

Results and grading will be added as `GRADING-1.md` and `results/`.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has checked the results unless a grading file says so. Code Apache-2.0; text and data CC BY 4.0.
