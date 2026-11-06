# Pre-registration: JOSS reference-matching audit 1

Written 2026-11-06 by AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com),
before the audit job (`ref_match_audit.py`) had run. Text CC BY 4.0, code Apache-2.0.

## Question

Crossref stores the reference list of every paper in the Journal of Open Source Software
(JOSS, DOI prefix `10.21105/joss.`). Each reference DOI is either supplied by the publisher
(`"doi-asserted-by": "publisher"`) or added afterwards by Crossref's own reference matcher
(`"doi-asserted-by": "crossref"`). JOSS papers cite a lot of software by name and URL only.
How often did Crossref's matcher link such a reference to an unrelated work, which then
receives a citation in Crossref (and in services built on it) that nobody gave it?

## What was seen before writing this

Only 49 JOSS records were read: the first 40 records published up to 2017 and 9 records
published from March 2026. Among the 2016-2017 records, 41 of 149 reference DOIs were
Crossref-asserted, and three of them looked wrong at a glance:

- 10.21105/joss.00024, ref2 "Foreman-Mackey, Daniel, corner.py on GitHub, 2016,
  https://github.com/dfm/corner.py" is linked to 10.12968/nuwa.2016.25.26, "Cookery corner"
  (Nursery World, 2016).
- 10.21105/joss.00236, ref1 "Mutel, Christopher, brightway2-data, 2016,
  https://brightwaylca.org/" is linked to 10.9790/1959-0504040105, "Knowledge And Attitude on
  Electro Convulsive Therapy Among Primary Care Givers" (IOSR Journal of Nursing and Health
  Science, 2016), whose first author is named Jeeva Christopher.
- 10.21105/joss.00236, ref9 "brightway2-analyzer" is linked to 10.4172/2161-0673.1000162.

Among the 2026 records, 1 of 124 reference DOIs was Crossref-asserted, and it was correct.
These three examples are used as unit tests of the scoring rule. Nothing else was looked at.

## Prior work (nearest) and the difference

- Cioffi et al. 2022 (Scientometrics 127:3593, arXiv:2111.11263): DOI-to-DOI citations in
  Crossref whose cited DOI does not exist. That is invalid DOIs, not valid DOIs of the wrong
  work, and it covers publisher-supplied DOIs.
- Kriváchy 2025 (arXiv:2511.01675) and Crossref's reply (community.crossref.org, topic
  15417, 2026-03-10): about 150k wrong links to Springer Nature "article number 1" papers,
  75% made by Crossref's matcher; matching changed on 2026-01-29; "Correcting historical data
  remains future work." That failure mode is page "1" versus article numbers in journal
  references. Software or URL-only references are not mentioned.
- Crossref's own matching evaluations (Tkaczyk 2018-2019, reference-matching-evaluation)
  use 2,000 sampled references; none is specific to software references.
- Software citation studies (e.g. arXiv:2306.17535) measure missing software citations, not
  wrong links.
- JOSS's editorialbot `check references` checks that author-supplied DOIs resolve; it never
  sees DOIs that Crossref adds after deposit.

No study was found that measures wrong Crossref-asserted links from a software journal's
reference lists, or tests whether such links still appear after the 2026-01-29 change.

## Method (fixed)

1. All works with prefix 10.21105 from `api.crossref.org/works` (cursor paging,
   `select=DOI,reference,deposited,published,issued,references-count`). JOSS works are those
   whose DOI starts `10.21105/joss.` (JOSE works are excluded).
2. One row per reference: citing DOI, publication year, last deposit date, key, DOI,
   doi-asserted-by, and the reference text (unstructured string plus any structured fields).
3. For every distinct Crossref-asserted DOI, the target's record from
   `api.crossref.org/works/<doi>`.
4. Score (function `score`): `title_cov` = share of the target title's content words
   (3+ letters, not stop words; dotted or hyphenated names such as `corner.py` are one word)
   found as words in the reference text; `surname_hit` = some target author family name
   (3+ letters) appears in the reference text; `year_hit`; `page_hit` = target first page
   (2+ characters) appears.
5. **Primary definition.** A link is *plausible* if `title_cov >= 0.6`, or if
   `surname_hit` and `year_hit` and `page_hit` all hold. Otherwise it is a *suspect*.
   Targets without title words are `no_title` and left out of rates.
   **Second definition (strict):** `title_cov < 0.3` and no surname hit.
6. Code-host references: text contains github.com, gitlab, bitbucket.org, sourceforge.net,
   codeberg.org, pypi, cran.r-project.org, bioconductor.org, juliahub.com, crates.io or
   npmjs.com.
7. Baseline: the 400 publisher-asserted references with 30+ characters of text that have the
   lowest sha256("pub|citing_doi|key"), scored the same way against the target's CSL-JSON
   from doi.org (works for Crossref and DataCite DOIs).
8. Descriptive only: for suspects (up to 1,500, lowest sha256), the top hit of Crossref's
   `query.bibliographic` search for the reference text, and whether it equals the linked DOI.
9. Grading samples: the 40 suspects and the 30 plausible links with the lowest
   sha256("citing_doi|key").

## Predictions

- **G (gate):** at least 3,700 JOSS works fetched, the cursor walk completed, and at least
  90% of Crossref-asserted target DOIs return a record. If G fails, nothing below is graded.
- **P1:** the number of Crossref-asserted reference DOIs in JOSS works is between 500 and
  10,000.
- **P2:** among references without a publisher DOI, the share Crossref matched is at least
  3 times higher for papers published 2016-2018 than for papers published 2024-2026.
- **P3:** at least 5% of judged Crossref-asserted links are suspects (primary definition).
- **P4:** the suspect rate among code-host references is at least 3 times the rate among
  other Crossref-asserted references (needs 20+ judged code-host links, otherwise not
  testable).
- **P5 (hand-graded):** at least 28 of the 40 sampled suspects are wrong links: the target
  is a different work from the one the reference cites. Another version of the same work
  (preprint, chapter, proceedings vs journal, erratum) counts as correct.
- **P6 (hand-graded):** at most 2 of the 30 sampled plausible links are wrong.
- **P7:** among references without a publisher DOI, suspects per reference in works last
  deposited on or after 2026-01-29 are fewer than half the rate in works deposited before.
- **P8:** at least one target DOI is a suspect link from 3 or more different JOSS papers.
- **P9:** the suspect rate among Crossref-asserted links is at least twice the suspect rate
  in the publisher-asserted baseline sample.

The job computes G, P1-P4 and P7-P9 mechanically in `summary.json`; P5 and P6 are graded by
reading each pair (the reference text against the target record, and the landing page when
unclear). Results will be published in GRADING-1.md whatever they are, including failures.

## What happens with the result

If wrong links are confirmed, the list goes to JOSS's editors and to Crossref through their
public channels, disclosed as made with AI agents. Crossref says re-deposited references are
matched with the new strategy, so a re-deposit by JOSS could be a fix; this audit does not
test that.
