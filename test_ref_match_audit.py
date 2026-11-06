# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for ref_match_audit.py (pure functions only; no network)."""
import unittest

import ref_match_audit as m

CORNER_REF = "Foreman-Mackey, Daniel, corner.py on GitHub, 2016, https://github.com/dfm/corner.py, 2016-05-26"
CORNER_TARGET = {"title": "Cookery corner", "container": "Nursery World", "families": [],
                 "year": 2016, "page": "", "volume": "2016"}
BRIGHTWAY_REF = "Mutel, Christopher, brightway2-data, 2016, https://brightwaylca.org/, 2017-04-05"
BRIGHTWAY_TARGET = {"title": "Knowledge And Attitude on Electro Convulsive Therapy Among Primary Care Givers",
                    "families": ["Christopher", ".S"], "year": 2016, "page": "01-05"}
BACON_REF = ("Bacon, P.-L., Harb, J., & Precup, D. (2017). The option-critic architecture. "
             "Proceedings of the Thirty-First AAAI Conference on Artificial Intelligence, 1726-1734.")
BACON_TARGET = {"title": "The Option-Critic Architecture", "families": ["Bacon", "Harb", "Precup"],
                "year": 2017, "page": ""}
ASTRO_REF = "Smith, J. A., & Jones, B. 2010, ApJ, 715, 1234"
ASTRO_TARGET = {"title": "A survey of something entirely described elsewhere",
                "families": ["Smith", "Jones"], "year": 2010, "page": "1234-1240"}


class Tokens(unittest.TestCase):
    def test_dotted_name_stays_one_word(self):
        self.assertIn("corner.py", m.joined_tokens(CORNER_REF))
        self.assertNotIn("corner", m.joined_tokens(CORNER_REF))
        self.assertIn("corner", m.all_tokens(CORNER_REF))

    def test_title_tokens_drop_stop_and_short(self):
        self.assertEqual(m.title_tokens("R: A language and environment for statistical computing"),
                         {"language", "environment", "statistical", "computing"})

    def test_fold_accents(self):
        self.assertEqual(m.fold("Caractérisation"), "caracterisation")

    def test_first_page(self):
        self.assertEqual(m.first_page("415-430"), "415")
        self.assertEqual(m.first_page("415–430"), "415")
        self.assertEqual(m.first_page(None), "")
        self.assertEqual(m.first_page("e1001"), "e1001")


class Scoring(unittest.TestCase):
    def test_corner_is_strict_suspect(self):
        sc = m.score(CORNER_REF, CORNER_TARGET)
        self.assertEqual(sc["title_cov"], 0.0)
        self.assertFalse(sc["surname_hit"])
        self.assertTrue(sc["year_hit"])
        self.assertEqual(m.verdict(sc), "suspect")
        self.assertTrue(m.strict_suspect(sc))

    def test_brightway_suspect_despite_given_name_hit(self):
        sc = m.score(BRIGHTWAY_REF, BRIGHTWAY_TARGET)
        self.assertTrue(sc["surname_hit"])  # 'Christopher' is the author's given name in the ref
        self.assertEqual(sc["title_cov"], 0.0)
        self.assertEqual(m.verdict(sc), "suspect")
        self.assertFalse(m.strict_suspect(sc))

    def test_bacon_plausible(self):
        sc = m.score(BACON_REF, BACON_TARGET)
        self.assertEqual(sc["title_cov"], 1.0)
        self.assertTrue(sc["surname_hit"])
        self.assertEqual(m.verdict(sc), "plausible")
        self.assertFalse(m.strict_suspect(sc))

    def test_titleless_astro_ref_plausible_by_biblio(self):
        sc = m.score(ASTRO_REF, ASTRO_TARGET)
        self.assertTrue(sc["surname_hit"] and sc["year_hit"] and sc["page_hit"])
        self.assertEqual(m.verdict(sc), "plausible")

    def test_no_title(self):
        sc = m.score("x", {"title": ""})
        self.assertEqual(sc["n_title_words"], 0)
        self.assertEqual(m.verdict(sc, has_title=False), "no_title")
        self.assertFalse(m.strict_suspect(sc, has_title=False))

    def test_short_surname_ignored(self):
        sc = m.score("Li, X. something 2019", {"title": "Other", "families": ["Li"], "year": 2019})
        self.assertFalse(sc["surname_hit"])


class Records(unittest.TestCase):
    def test_ref_text_joins_fields(self):
        t = m.ref_text({"key": "k", "author": "Gregory", "year": "2019",
                        "article-title": "Concepts", "journal-title": "Surveys in Geophysics"})
        self.assertEqual(t, "Gregory | 2019 | Concepts | Surveys in Geophysics")
        self.assertEqual(m.ref_text(None), "")

    def test_code_host_and_url(self):
        self.assertTrue(m.is_code_host_ref(CORNER_REF))
        self.assertFalse(m.is_code_host_ref(BRIGHTWAY_REF))
        self.assertTrue(m.has_url(BRIGHTWAY_REF))
        self.assertFalse(m.has_url(BACON_REF))

    def test_summarize_crossref_work(self):
        s = m.summarize_crossref_work({"title": ["Cookery corner"], "container-title": ["Nursery World"],
                                       "issued": {"date-parts": [[2016, 12, 12]]}, "type": "journal-article",
                                       "is-referenced-by-count": 6, "author": [{"family": "X", "given": "Y"}]})
        self.assertEqual(s["title"], "Cookery corner")
        self.assertEqual(s["year"], 2016)
        self.assertEqual(s["families"], ["X"])
        self.assertEqual(s["cited_by"], 6)
        self.assertEqual(m.summarize_crossref_work({})["year"], None)

    def test_summarize_csl(self):
        s = m.summarize_csl({"title": "T", "author": [{"family": "F"}, {"literal": "Org"}],
                             "issued": {"date-parts": [[2020]]}, "page": "1-2"})
        self.assertEqual(s["families"], ["F", "Org"])
        self.assertEqual(s["year"], 2020)
        self.assertEqual(m.summarize_csl({"issued": "bad"})["year"], None)

    def test_flatten_and_eras(self):
        items = [
            {"DOI": "10.21105/joss.00024", "published": {"date-parts": [[2016]]},
             "deposited": {"date-time": "2019-01-01T00:00:00Z"},
             "reference": [{"key": "ref1", "DOI": "10.1109/X", "doi-asserted-by": "publisher"},
                           {"key": "ref2", "DOI": "10.12968/Y", "doi-asserted-by": "crossref",
                            "unstructured": CORNER_REF},
                           {"key": "ref3", "unstructured": "no doi"}]},
            {"DOI": "10.21105/joss.10000", "published": {"date-parts": [[2026]]},
             "deposited": {"date-time": "2026-03-01T00:00:00Z"},
             "reference": [{"key": "a", "unstructured": "n1"}, {"key": "b", "unstructured": "n2"}]},
            {"DOI": "10.21105/jose.00001", "reference": [{"key": "z", "unstructured": "x"}]},
        ]
        rows = m.flatten_refs(items)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[1]["ref_doi"], "10.12968/y")
        e = m.era_rates(rows)
        self.assertEqual(e["2016-2018"], {"pool": 2, "matched": 1, "rate": 0.5})
        self.assertEqual(e["2024-2026"]["matched"], 0)
        self.assertFalse(m.unlinked_or_matched(rows[0]))

    def test_era_of(self):
        self.assertEqual(m.era_of(2016), "2016-2018")
        self.assertEqual(m.era_of(2020), "2019-2020")
        self.assertEqual(m.era_of(2023), "2021-2023")
        self.assertEqual(m.era_of(2026), "2024-2026")
        self.assertEqual(m.era_of(None), "unknown")

    def test_lowest_sample_is_deterministic(self):
        rows = [{"citing_doi": "d%d" % i, "key": "k"} for i in range(50)]
        a = m.lowest(rows, 5, lambda r: m.sha_key(r["citing_doi"], r["key"]))
        b = m.lowest(list(reversed(rows)), 5, lambda r: m.sha_key(r["citing_doi"], r["key"]))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)

    def test_rate(self):
        self.assertIsNone(m.rate(1, 0))
        self.assertEqual(m.rate(1, 4), 0.25)


if __name__ == "__main__":
    unittest.main()
