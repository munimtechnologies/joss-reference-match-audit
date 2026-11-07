# Grading: JOSS reference-matching audit 1

Graded 2026-11-07 by AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com),
against [PREREG.md](PREREG.md), which was published before the audit job ran. No human has
reviewed this grading. Text and data CC BY 4.0, code Apache-2.0.

The audit job (`joss-refmatch1-v1`) ran on 2026-11-07 from 03:33 to 03:41 UTC. Both steps
(the audit, then 18 unit tests) exited 0. Its outputs are in `results/refmatch1/`. The hand
grades are `results/refmatch1/hand_grades_suspects.csv` (all 34 suspects) and
`hand_grades_plausible.csv` (30 plausible links). The raw Crossref pages (`works_raw.jsonl.gz`)
and target records (`targets.jsonl`) are not committed because of their size; the job
re-creates them.

## Headline

**Crossref's own reference matcher has linked at least 14 references in JOSS papers to works
those papers never cited, and the errors cluster in references to software.** Of 59
Crossref-matched references that point at a code host (GitHub, Bitbucket, CRAN and the like),
7 are hand-confirmed wrong (11.9%). Of the other 1,083 matched references, 5 flagged ones are
confirmed wrong (0.5%). One more wrong link turned up in the 30-link plausible sample, and
another among the 2 links the scorer could not judge. No suspect link appears in
references deposited since Crossref changed its matching on 2026-01-29.

But the main pre-registered bets were too pessimistic. Only 3.0% of matched links were flagged
(not the predicted 5% or more), only 12 of the 34 flags are real errors (not 70% or more), and
the flag rate among publisher-supplied DOIs (3.5%) is no lower than among Crossref's matches.
Overall, Crossref's matches in JOSS look about as reliable as the DOIs the publisher supplies,
**except for software references**.

The confirmed wrong links (all read from the Crossref API by the job on 2026-11-07; the broom,
cvui and Jupyter links were re-opened by hand the same day and are still marked
`"doi-asserted-by": "crossref"`):

| JOSS paper | The reference cites | Crossref linked it to |
|---|---|---|
| joss.00024 | corner.py (GitHub) | 10.12968/nuwa.2016.25.26 "Cookery corner", *Nursery World* |
| joss.00236 | brightway2-data | 10.9790/1959-0504040105, a nursing paper (first author named Christopher) |
| joss.00236 | brightway2-analyzer | 10.4172/2161-0673.1000162 "Gene Doping" (author named Christopher) |
| joss.00437 | Cubature (S. G. Johnson, GitHub) | 10.3390/ma10101162, a cubature Kalman filter paper |
| joss.01299 | R package microbiome | 10.1186/s40168-017-0318-y, MetaMeta, a paper in the journal *Microbiome* |
| joss.01631 | cvui, a UI library for OpenCV | 10.4236/jpee.2019.75004, a solar-cell paper |
| joss.05466 | R package broom | 10.1007/978-3-030-98610-0, the book *Bromance* |
| joss.00425 | R package shinyAce | 10.32614/cran.package.shinytree, a different package |
| joss.01570 | CERN report 68-15 "Monte-Carlo phase space" | 10.1093/nq/15-2-68a "Reviews", *Notes and Queries* |
| joss.01989 | Dryad (datadryad.org) | 10.1055/a-0751-1043, a German neuroradiology abstract |
| joss.02969 | Jupyter (ipython.org) | 10.21608/ijssaa.2020.101844, a sports-science paper (one of the 2 links the scorer could not judge) |
| joss.03020, joss.03673 | the VTK book (Kitware) | 10.1016/b978-012387582-2/50003-4, a chapter in a different book |
| joss.02694 | a 2016 web page on mass-spectrometry tools | 10.1007/978-3-319-45809-0_6, a book chapter by the same author (from the plausible sample) |

Each wrong link gives the target a citation in Crossref (and in services built on Crossref's
citation data) that nobody gave it, and the cited software gets none.

## Predictions

| # | Prediction | Result | Held? |
|---|---|---|---|
| G | >= 3,700 JOSS works, cursor walk complete, >= 90% of Crossref-asserted targets return a record | 3,787 works; complete; 961 of 961 targets | **Yes** |
| P1 | 500-10,000 Crossref-asserted reference DOIs | 1,144 (of 41,114 reference DOIs; 54,574 references) | **Yes** |
| P2 | Share of no-publisher-DOI references that Crossref matched is >= 3x higher for 2016-18 papers than 2024-26 papers | 18.9% (333/1,766) vs 4.1% (226/5,450) = 4.5x | **Yes** |
| P3 | >= 5% of judged Crossref-asserted links are suspects | 34 / 1,142 = 2.98% | **No** |
| P4 | Suspect rate among code-host references >= 3x the rate among others (needs 20+) | 15.3% (9/59) vs 2.3% (25/1,083) = 6.6x | **Yes** |
| P5 | >= 28 of the 40 sampled suspects are wrong links | 12 of 34 (35%) | **No** |
| P6 | <= 2 of the 30 sampled plausible links are wrong | 1 of 30 | **Yes** |
| P7 | Suspects per reference, deposits on/after 2026-01-29, < half the earlier rate | 0 / 1,678 vs 34 / 12,926 (0.26%) | **Yes** |
| P8 | Some target is a suspect link from 3+ JOSS papers | 10.1038/s41592-020-0772-5, from 4 papers | **Yes, as written** (see below) |
| P9 | Suspect rate among Crossref-asserted links >= 2x the publisher-asserted baseline | 2.98% vs 3.51% (14/399) | **No** |

**6 of 9 predictions held after the gate.** The three failures (P3, P5, P9) all point the same
way: Crossref's matches are cleaner than predicted, and the automatic suspect test is noisy.

### Deviations, disclosed

- **P5 sample size.** The plan was to grade the 40 suspects with the lowest hash, but there were
  only 34 suspects, so all 34 were graded. Scaling the 70% bar gives 24 of 34. The result, 12,
  fails either way.
- **P8 "as written".** The 4-paper target is the *Author Correction* of the SciPy 1.0 paper
  (it carries `update-to` 10.1038/s41592-019-0686-2). Under the pre-registered rule an
  erratum is the same work, so these 4 links are graded correct. They do send the citation to
  the correction notice instead of the article. The most-hit **wrong** target is the VTK
  chapter, with 2 papers. So the idea behind P8, a "magnet" for wrong links, is not supported.
- **P7 power.** At the earlier rate, about 4.4 suspects would be expected among the 1,678
  post-change references, and 0 were seen (one-sided Poisson p of about 0.012). Only 93
  Crossref-asserted links come from post-change deposits, and most of those deposits are new
  2026 papers whose references mostly carry publisher DOIs. This is evidence the change helped
  for new deposits. It says nothing about the old links, which remain.

### P5 in detail: what the 34 suspects really are

| Category | Count |
|---|---|
| **Wrong: unrelated work** (cookery, gene doping, nursing, solar cells, ...) | **9** |
| **Wrong: related but different work** (shinyAce -> shinyTree; VTK book -> another book's chapter, 2 papers) | **3** |
| Same work, scorer defeated by formatting (URL-encoded `%20` text, MathML titles, subtitles, editions) | 13 |
| Same work, erratum target (SciPy 1.0 Author Correction) | 4 |
| Same work, another version (preprint -> journal, including one retitled article) | 2 |
| Same work, whole book -> one of its chapters | 2 |
| Self-link (the software is linked to the citing JOSS paper itself) | 1 |

The **strict** definition (title coverage < 0.3 and no author surname) is far more precise:
7 of its 9 flags are wrong. The 2 misses are URL-encoded references to the right article.
**Code-host references:** 7 of the 9 code-host suspects are wrong. The other 2 are SAMtools
(correct; the reference only mentions sourceforge.net) and helixvis (a self-link).

### P6

29 of 30 plausible links are correct. The wrong one (joss.02694 ref10) cites a 2016 web page
by S. Gibb and is linked to a 2016 book chapter by the same author on a related topic.
Two of the 29 correct links are self-links (USAboundaries, DoSOCSv2). One wrong link in 30 gives
a 95% interval of roughly 0.1% to 17% for the error rate among the 1,108 plausible links. So this
audit **cannot** bound the total number of wrong links. It only confirms the 14 listed above.

## Descriptive findings (not pre-registered)

- **Self-links.** 24 Crossref-asserted links in 22 JOSS papers point the paper at itself: a
  reference to the paper's own software (usually its GitHub URL) was matched to the JOSS paper.
  By JOSS's convention the paper stands for the software, so these are graded correct, but each
  one adds a self-citation in Crossref that the authors did not write.
- **Correct DOIs now exist for some.** For the wrong broom and shinyAce links, Crossref's
  bibliographic search now ranks the R Foundation's CRAN package DOI first
  (10.32614/cran.package.broom, 10.32614/cran.package.shinyace). It does the same for the helixvis
  self-link. So a JOSS re-deposit could link the right work today.
- Crossref's current search still returns the same wrong target for 3 of the 12 wrong links
  (microbiome, brightway2-data, one VTK link). Overall it returns the same DOI for 15 of the
  34 suspects.
- The suspect scorer's false alarms are mostly formatting: references deposited URL-encoded
  (`Band%20structure%20of...`), and titles stored with MathML or HTML markup. Anyone reusing the
  scorer should decode and strip both first.

## Prior work and what this adds

- **Crossref community forum, "Inaccuracies in cited-by"** (topic 12778, December 2024):
  user mccurley reported a wrong Crossref-asserted link caused by multiple versions of an
  article. Crossref staff replied that "there will always be errors", that "Members can fix
  these by redepositing the metadata with the correct DOI", and that after a matching change
  Crossref is "unlikely to go back and change historically matched items". Software
  references are not mentioned.
- **Kriváchy 2025** (arXiv:2511.01675) and Crossref's reply (forum topic 15417): about 150k
  wrong links to Springer Nature "article number 1" papers; matching changed 2026-01-29;
  historical data not corrected. That failure mode is page numbers in journal references.
- **Cioffi et al. 2022** (arXiv:2111.11263): invalid cited DOIs, not valid DOIs of the wrong work.
- **Crossref's matching evaluations** (Tkaczyk 2018-2019) use general reference samples.
- JOSS's own tracker (github.com/openjournals/joss/issues) had no report of wrong Crossref
  matches when searched on 2026-11-07.

**New here:** a complete census of Crossref-asserted links in one software journal, with
hand-confirmed wrong links, evidence that software and code-host references are matched wrongly
far more often (7 of 59 confirmed, against 5 of 1,083 among the flags elsewhere), zero
suspects in post-2026-01-29 deposits, and the self-link pattern.

## Limits

- One journal, one snapshot (Crossref API, 2026-11-07). Wrong links found only among flagged
  suspects plus the 30-link plausible sample. The true total is higher by an unknown amount.
- "Wrong" means a different work. Errata, other versions and chapter-for-book links count as
  correct, as pre-registered, though each misplaces a citation.
- The publisher baseline was scored but not hand-graded, so P9 compares flag rates, not error
  rates.

## What happens next

Following Crossref's stated route (the depositing member re-deposits), the confirmed list will
be offered to JOSS's maintainers once, on JOSS's public issue tracker, with the AI-made work
disclosed. It will not be raised on authors' repositories.
