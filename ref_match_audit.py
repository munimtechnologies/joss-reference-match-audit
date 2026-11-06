# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""JOSS reference-matching audit 1.

Crossref stores the reference list of every Journal of Open Source Software (JOSS) paper.
A reference DOI is either supplied by the publisher ("doi-asserted-by": "publisher") or
added later by Crossref's own reference matcher ("doi-asserted-by": "crossref"). This
script asks how often Crossref's matcher linked a JOSS reference -- often a piece of
software cited only by name and URL -- to an unrelated work, which then receives a
citation it never got.

For every JOSS work in Crossref (DOI prefix 10.21105/joss.):
  - reads its reference list, publication year and last deposit date;
  - for every Crossref-asserted reference DOI, reads the target's Crossref record and
    scores whether the target plausibly is the cited work (title words, author surname,
    year, first page found in the reference text);
  - as a baseline, scores a fixed sample of publisher-asserted references the same way
    (target metadata from doi.org content negotiation, so DataCite DOIs work too);
  - for each suspect link, asks Crossref's bibliographic search whether its top hit for
    the reference text is still the same target (descriptive only).
No API keys. Sources: api.crossref.org, doi.org.

Usage: python ref_match_audit.py --out-dir /out [--max-pages N]
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

MAILTO = "mv2@munimtech.com"
UA = "joss-reference-match-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
WORKS_URL = ("https://api.crossref.org/works?filter=prefix:10.21105&rows=100"
             "&select=DOI,reference,deposited,published,issued,references-count"
             "&mailto=" + MAILTO + "&cursor={cursor}")
WORK_URL = "https://api.crossref.org/works/{doi}?mailto=" + MAILTO
BIBLIO_URL = ("https://api.crossref.org/works?rows=1&select=DOI,score&mailto=" + MAILTO
              + "&query.bibliographic={q}")
CSL_URL = "https://doi.org/{doi}"
CSL_ACCEPT = "application/vnd.citationstyles.csl+json"

FIX_DATE = "2026-01-29"          # Crossref changed its matching strategy on this date
PUBLISHER_SAMPLE = 400
GRADE_SUSPECTS = 40
GRADE_PLAUSIBLE = 30
BIBLIO_CAP = 1500
BIBLIO_TIME_BUDGET_S = 110 * 60  # skip the descriptive search step after this much time

CODE_HOSTS = ("github.com", "gitlab.com", "gitlab.", "bitbucket.org", "sourceforge.net",
              "codeberg.org", "pypi.org", "pypi.python.org", "cran.r-project.org",
              "bioconductor.org", "juliahub.com", "crates.io", "npmjs.com")
STOP = {
    "the", "and", "for", "with", "from", "into", "using", "use", "via", "its", "are", "was",
    "were", "can", "not", "but", "has", "have", "this", "that", "these", "those", "their",
    "our", "your", "der", "die", "das", "und", "les", "des", "del", "por", "para", "con",
    "une", "est", "von", "zur", "how", "what", "why", "when", "who", "which", "all", "any",
    "new", "towards", "toward", "between", "among", "within", "without", "upon", "about",
}
WORD_RE = re.compile(r"[a-z0-9]+(?:[._\-][a-z0-9]+)*")


# ---------------------------------------------------------------- pure helpers
def fold(s):
    """ASCII-folded lower-case text."""
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()


def joined_tokens(s):
    """Words of the text; dotted/hyphenated names such as 'corner.py' stay one word."""
    return WORD_RE.findall(fold(s))


def title_tokens(s):
    """Content words (>= 3 characters, not stop words) used to compare titles."""
    return {w for w in joined_tokens(s) if len(w) >= 3 and w not in STOP}


def all_tokens(s):
    """Every word of the text plus the parts of dotted/hyphenated words."""
    out = set()
    for w in joined_tokens(s):
        out.add(w)
        for p in re.split(r"[._\-]", w):
            if p:
                out.add(p)
    return out


def ref_text(ref):
    """One string with everything a deposited reference says about the cited work."""
    if not isinstance(ref, dict):
        return ""
    parts = []
    for k in ("unstructured", "author", "year", "article-title", "volume-title",
              "series-title", "journal-title", "volume", "issue", "first-page", "edition"):
        v = ref.get(k)
        if v is None:
            continue
        v = str(v).strip()
        if v and v not in parts:
            parts.append(v)
    return " | ".join(parts)


def is_code_host_ref(text):
    t = fold(text)
    return any(h in t for h in CODE_HOSTS)


def has_url(text):
    return bool(re.search(r"https?://|www\.", fold(text)))


def first_page(page):
    if page is None:
        return ""
    p = re.split(r"[-–—,]", str(page).strip())[0].strip()
    return fold(p)


def summarize_crossref_work(msg):
    """Normalized metadata of a Crossref /works/<doi> message."""
    msg = msg or {}

    def first(v):
        if isinstance(v, list):
            return str(v[0]) if v else ""
        return str(v or "")

    year = None
    for k in ("issued", "published", "published-print", "published-online", "created"):
        dp = ((msg.get(k) or {}).get("date-parts") or [[None]])
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
            break
    fams = []
    for a in msg.get("author") or []:
        if isinstance(a, dict):
            fams.append(str(a.get("family") or a.get("name") or ""))
    return {"title": first(msg.get("title")), "container": first(msg.get("container-title")),
            "families": [f for f in fams if f], "year": year, "page": str(msg.get("page") or ""),
            "volume": str(msg.get("volume") or ""), "type": str(msg.get("type") or ""),
            "publisher": str(msg.get("publisher") or ""),
            "cited_by": msg.get("is-referenced-by-count")}


def summarize_csl(js):
    """Normalized metadata of a CSL-JSON record from doi.org content negotiation."""
    js = js or {}

    def first(v):
        if isinstance(v, list):
            return str(v[0]) if v else ""
        return str(v or "")

    year = None
    for k in ("issued", "published", "created"):
        dp = ((js.get(k) or {}).get("date-parts") or [[None]]) if isinstance(js.get(k), dict) else [[None]]
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
            break
    fams = []
    for a in js.get("author") or []:
        if isinstance(a, dict):
            fams.append(str(a.get("family") or a.get("literal") or ""))
    return {"title": first(js.get("title")), "container": first(js.get("container-title")),
            "families": [f for f in fams if f], "year": year, "page": str(js.get("page") or ""),
            "volume": str(js.get("volume") or ""), "type": str(js.get("type") or ""),
            "publisher": str(js.get("publisher") or ""), "cited_by": None}


def score(text, target):
    """Evidence that the target record is the work the reference text cites."""
    tt = title_tokens(target.get("title"))
    rjoined = set(joined_tokens(text))
    rall = all_tokens(text)
    cov = (len([w for w in tt if w in rjoined]) / len(tt)) if tt else 0.0
    sur = False
    for fam in target.get("families") or []:
        parts = [p for p in re.findall(r"[a-z0-9]+", fold(fam)) if len(p) >= 2]
        if parts and len("".join(parts)) >= 3 and all(p in rall for p in parts):
            sur = True
            break
    yr = target.get("year")
    year_hit = bool(yr) and str(yr) in rall
    fp = first_page(target.get("page"))
    page_hit = len(fp) >= 2 and fp in rall
    return {"title_cov": round(cov, 3), "n_title_words": len(tt), "surname_hit": sur,
            "year_hit": year_hit, "page_hit": page_hit}


def verdict(sc, has_title=True):
    """'plausible' or 'suspect' (primary definition, fixed in PREREG.md)."""
    if not has_title:
        return "no_title"
    strong = sc["title_cov"] >= 0.6
    biblio = sc["surname_hit"] and sc["year_hit"] and sc["page_hit"]
    return "plausible" if (strong or biblio) else "suspect"


def strict_suspect(sc, has_title=True):
    """Second, stricter definition: few title words and no author surname at all."""
    return bool(has_title) and sc["title_cov"] < 0.3 and not sc["surname_hit"]


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def lowest(rows, n, keyf):
    return sorted(rows, key=keyf)[:n]


def rate(num, den):
    return (num / den) if den else None


def era_of(year):
    if year is None:
        return "unknown"
    if year <= 2018:
        return "2016-2018"
    if year <= 2020:
        return "2019-2020"
    if year <= 2023:
        return "2021-2023"
    return "2024-2026"


def work_year(item):
    for k in ("published", "issued"):
        dp = ((item.get(k) or {}).get("date-parts") or [[None]])
        if dp and dp[0] and dp[0][0]:
            return dp[0][0]
    return None


def deposited_iso(item):
    return str(((item.get("deposited") or {}).get("date-time")) or "")


def flatten_refs(items):
    """One row per reference of every JOSS work."""
    rows = []
    for it in items:
        doi = str(it.get("DOI", "")).lower()
        if not doi.startswith("10.21105/joss."):
            continue
        yr = work_year(it)
        dep = deposited_iso(it)
        for i, ref in enumerate(it.get("reference") or []):
            if not isinstance(ref, dict):
                continue
            rd = str(ref.get("DOI") or "").strip().lower()
            rows.append({"citing_doi": doi, "year": yr, "deposited": dep,
                         "key": str(ref.get("key") or "ref%d" % (i + 1)),
                         "ref_doi": rd, "asserted_by": str(ref.get("doi-asserted-by") or ""),
                         "text": ref_text(ref)})
    return rows


def unlinked_or_matched(r):
    """True for references that had no publisher DOI (the pool Crossref matches from)."""
    return not (r["ref_doi"] and r["asserted_by"] == "publisher")


def era_rates(rows):
    """Per era: references without a publisher DOI, how many Crossref matched, the rate."""
    den, num = collections.Counter(), collections.Counter()
    for r in rows:
        if unlinked_or_matched(r):
            e = era_of(r["year"])
            den[e] += 1
            if r["asserted_by"] == "crossref" and r["ref_doi"]:
                num[e] += 1
    return {e: {"pool": den[e], "matched": num[e], "rate": rate(num[e], den[e])}
            for e in sorted(den)}


# ---------------------------------------------------------------- network
class Pacer:
    def __init__(self, per_second):
        self.gap = 1.0 / per_second
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)


PACE = {"crossref": Pacer(4), "doi": Pacer(3)}
STATS = collections.Counter()


def http_get(url, pacer, accept=None, tries=5, timeout=60):
    """(status, body). 404/410 definitive; -1 = network failure."""
    delay = 5
    last = -1
    for _ in range(tries):
        pacer.wait()
        h = {"User-Agent": UA}
        if accept:
            h["Accept"] = accept
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["http_%d" % r.status] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            STATS["http_%d" % e.code] += 1
            if e.code in (404, 410):
                return e.code, b""
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return e.code, b""
        except Exception:
            STATS["http_neterr"] += 1
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


def fetch_works(max_pages):
    items, cursor = [], "*"
    for page in range(max_pages):
        st, body = http_get(WORKS_URL.format(cursor=urllib.parse.quote(cursor, safe="")),
                            PACE["crossref"])
        if st != 200:
            print("works page %d failed: %s" % (page, st), file=sys.stderr)
            return items, False
        msg = json.loads(body.decode("utf-8")).get("message") or {}
        batch = msg.get("items") or []
        if not batch:
            return items, True
        items.extend(batch)
        cursor = msg.get("next-cursor") or ""
        if not cursor:
            return items, True
        if page % 5 == 0:
            print("works: %d after page %d" % (len(items), page + 1), flush=True)
    return items, False


def fetch_target(doi):
    st, body = http_get(WORK_URL.format(doi=urllib.parse.quote(doi, safe="/")), PACE["crossref"])
    if st != 200:
        return st, None
    try:
        return st, summarize_crossref_work(json.loads(body.decode("utf-8")).get("message"))
    except Exception:
        return -2, None


def fetch_csl(doi):
    st, body = http_get(CSL_URL.format(doi=urllib.parse.quote(doi, safe="/")), PACE["doi"],
                        accept=CSL_ACCEPT)
    if st != 200:
        return st, None
    try:
        return st, summarize_csl(json.loads(body.decode("utf-8")))
    except Exception:
        return -2, None


def biblio_top(text):
    q = urllib.parse.quote(text[:300])
    st, body = http_get(BIBLIO_URL.format(q=q), PACE["crossref"])
    if st != 200:
        return st, "", None
    try:
        its = (json.loads(body.decode("utf-8")).get("message") or {}).get("items") or []
    except Exception:
        return -2, "", None
    if not its:
        return st, "", None
    return st, str(its[0].get("DOI", "")).lower(), its[0].get("score")


# ---------------------------------------------------------------- main
def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=200)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    items, complete = fetch_works(a.max_pages)
    with gzip.open(os.path.join(a.out_dir, "works_raw.jsonl.gz"), "wt", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    joss = [it for it in items if str(it.get("DOI", "")).lower().startswith("10.21105/joss.")]
    print("fetched %d works (%d JOSS), complete=%s" % (len(items), len(joss), complete), flush=True)
    rows = flatten_refs(items)
    with_doi = [r for r in rows if r["ref_doi"]]
    cref = [r for r in with_doi if r["asserted_by"] == "crossref"]
    pubr = [r for r in with_doi if r["asserted_by"] == "publisher"]

    # Crossref-asserted targets
    targets, tstatus = {}, collections.Counter()
    for i, d in enumerate(sorted({r["ref_doi"] for r in cref})):
        st, meta = fetch_target(d)
        tstatus[str(st)] += 1
        targets[d] = {"status": st, "meta": meta}
        if i % 250 == 0:
            print("targets: %d" % i, flush=True)
    with open(os.path.join(a.out_dir, "targets.jsonl"), "w", encoding="utf-8") as f:
        for d, v in sorted(targets.items()):
            f.write(json.dumps({"doi": d, **v}, ensure_ascii=False) + "\n")

    def scored(r, meta):
        if not meta:
            return dict(r, verdict="lookup_failed", strict=False)
        has_title = bool(title_tokens(meta.get("title")))
        sc = score(r["text"], meta)
        return dict(r, **sc, verdict=verdict(sc, has_title), strict=strict_suspect(sc, has_title),
                    target_title=meta.get("title"), target_container=meta.get("container"),
                    target_year=meta.get("year"), target_type=meta.get("type"),
                    target_families="; ".join((meta.get("families") or [])[:4]),
                    target_publisher=meta.get("publisher"), target_cited_by=meta.get("cited_by"),
                    code_host=is_code_host_ref(r["text"]), has_url=has_url(r["text"]),
                    after_fix=r["deposited"][:10] >= FIX_DATE if r["deposited"] else None)

    cs = [scored(r, (targets.get(r["ref_doi"]) or {}).get("meta")) for r in cref]
    fields = ["citing_doi", "year", "deposited", "after_fix", "key", "ref_doi", "verdict",
              "strict", "title_cov", "n_title_words", "surname_hit", "year_hit", "page_hit",
              "code_host", "has_url", "text", "target_title", "target_container", "target_year",
              "target_type", "target_families", "target_publisher", "target_cited_by"]
    write_csv(os.path.join(a.out_dir, "crossref_asserted.csv"), cs, fields)
    sus = [r for r in cs if r["verdict"] == "suspect"]
    pla = [r for r in cs if r["verdict"] == "plausible"]

    # descriptive: does Crossref's bibliographic search still return the same target?
    bib_rows = []
    for r in lowest(sus, BIBLIO_CAP, lambda r: sha_key(r["citing_doi"], r["key"])):
        if time.monotonic() - t0 > BIBLIO_TIME_BUDGET_S:
            break
        st, top, sc = biblio_top(r["text"])
        bib_rows.append({"citing_doi": r["citing_doi"], "key": r["key"], "ref_doi": r["ref_doi"],
                         "status": st, "top_doi": top, "top_score": sc,
                         "same_as_link": top == r["ref_doi"]})
    write_csv(os.path.join(a.out_dir, "suspect_search_check.csv"), bib_rows,
              ["citing_doi", "key", "ref_doi", "status", "top_doi", "top_score", "same_as_link"])
    sus_out = []
    bmap = {(b["citing_doi"], b["key"]): b for b in bib_rows}
    for r in sorted(sus, key=lambda r: (r["citing_doi"], r["key"])):
        b = bmap.get((r["citing_doi"], r["key"])) or {}
        sus_out.append(dict(r, search_top=b.get("top_doi", ""), search_same=b.get("same_as_link", "")))
    write_csv(os.path.join(a.out_dir, "suspects.csv"), sus_out, fields + ["search_top", "search_same"])

    # grading samples (fixed in PREREG.md)
    g_s = lowest(sus, GRADE_SUSPECTS, lambda r: sha_key(r["citing_doi"], r["key"]))
    g_p = lowest(pla, GRADE_PLAUSIBLE, lambda r: sha_key(r["citing_doi"], r["key"]))
    gfields = fields + ["grade", "note"]
    write_csv(os.path.join(a.out_dir, "grade_suspects40.csv"), g_s, gfields)
    write_csv(os.path.join(a.out_dir, "grade_plausible30.csv"), g_p, gfields)

    # baseline: publisher-asserted references with text
    pub_text = [r for r in pubr if len(r["text"]) >= 30]
    psample = lowest(pub_text, PUBLISHER_SAMPLE, lambda r: sha_key("pub", r["citing_doi"], r["key"]))
    pscored, pstatus = [], collections.Counter()
    for r in psample:
        st, meta = fetch_csl(r["ref_doi"])
        pstatus[str(st)] += 1
        pscored.append(scored(r, meta))
    write_csv(os.path.join(a.out_dir, "publisher_sample.csv"), pscored, fields)
    p_ok = [r for r in pscored if r["verdict"] in ("suspect", "plausible")]
    p_sus = [r for r in p_ok if r["verdict"] == "suspect"]

    # summary + mechanical predictions
    judged = [r for r in cs if r["verdict"] in ("suspect", "plausible")]
    sus_rate = rate(len(sus), len(judged))
    ch = [r for r in judged if r["code_host"]]
    nch = [r for r in judged if not r["code_host"]]
    ch_rate, nch_rate = rate(sum(r["verdict"] == "suspect" for r in ch), len(ch)), \
        rate(sum(r["verdict"] == "suspect" for r in nch), len(nch))
    eras = era_rates(rows)
    e_old = (eras.get("2016-2018") or {}).get("rate")
    e_new = (eras.get("2024-2026") or {}).get("rate")
    pool_after = [r for r in rows if unlinked_or_matched(r) and r["deposited"][:10] >= FIX_DATE]
    pool_before = [r for r in rows if unlinked_or_matched(r) and r["deposited"]
                   and r["deposited"][:10] < FIX_DATE]
    s_after = sum(1 for r in sus if r["after_fix"] is True)
    s_before = sum(1 for r in sus if r["after_fix"] is False)
    r_after, r_before = rate(s_after, len(pool_after)), rate(s_before, len(pool_before))
    magnets = collections.Counter()
    seen_pairs = set()
    for r in sus:
        if (r["ref_doi"], r["citing_doi"]) not in seen_pairs:
            seen_pairs.add((r["ref_doi"], r["citing_doi"]))
            magnets[r["ref_doi"]] += 1
    tgt_ok = sum(1 for v in targets.values() if v["meta"])
    p_rate = rate(len(p_sus), len(p_ok))
    strict_n = sum(1 for r in judged if r["strict"])

    def holds(cond):
        return None if cond is None else bool(cond)

    pred = {
        "G": holds(len(joss) >= 3700 and complete and (rate(tgt_ok, len(targets)) or 0) >= 0.90),
        "P1": holds(500 <= len(cref) <= 10000),
        "P2": holds(None if e_old is None or e_new is None else
                    (e_old > 0 and (e_new == 0 or e_old >= 3 * e_new))),
        "P3": holds(None if sus_rate is None else sus_rate >= 0.05),
        "P4": holds(None if (len(ch) < 20 or ch_rate is None or nch_rate is None) else
                    (ch_rate >= 3 * nch_rate if nch_rate > 0 else ch_rate > 0)),
        "P5": "hand-graded (grade_suspects40.csv)",
        "P6": "hand-graded (grade_plausible30.csv)",
        "P7": holds(None if r_after is None or r_before is None else
                    (r_before > 0 and r_after < 0.5 * r_before)),
        "P8": holds(bool(magnets) and magnets.most_common(1)[0][1] >= 3),
        "P9": holds(None if (sus_rate is None or p_rate is None) else
                    (sus_rate >= 2 * p_rate if p_rate > 0 else sus_rate > 0)),
    }
    summary = {
        "works_fetched": len(items), "joss_works": len(joss), "fetch_complete": complete,
        "joss_works_with_refs": sum(1 for it in joss if it.get("reference")),
        "refs": len(rows), "refs_with_doi": len(with_doi),
        "asserted_by": dict(collections.Counter(r["asserted_by"] for r in with_doi)),
        "crossref_asserted": len(cref), "crossref_asserted_targets": len(targets),
        "target_status": dict(tstatus), "targets_ok": tgt_ok,
        "judged": len(judged), "suspects": len(sus), "plausible": len(pla),
        "suspect_rate": sus_rate, "strict_suspects": strict_n,
        "strict_rate": rate(strict_n, len(judged)),
        "verdicts": dict(collections.Counter(r["verdict"] for r in cs)),
        "code_host_judged": len(ch), "code_host_suspect_rate": ch_rate,
        "other_judged": len(nch), "other_suspect_rate": nch_rate,
        "suspects_with_url": sum(1 for r in sus if r["has_url"]),
        "era_rates": eras,
        "fix_date": FIX_DATE,
        "pool_after_fix": len(pool_after), "suspects_after_fix": s_after, "rate_after_fix": r_after,
        "pool_before_fix": len(pool_before), "suspects_before_fix": s_before,
        "rate_before_fix": r_before,
        "crossref_asserted_after_fix": sum(1 for r in cs if r.get("after_fix") is True),
        "top_magnets": magnets.most_common(15),
        "suspect_targets_distinct": len(magnets),
        "suspect_target_types": dict(collections.Counter(r.get("target_type") for r in sus)),
        "suspect_target_publishers": collections.Counter(r.get("target_publisher") for r in sus).most_common(15),
        "search_checked": len(bib_rows),
        "search_same_as_link": sum(1 for b in bib_rows if b["same_as_link"]),
        "publisher_sample": len(psample), "publisher_sample_status": dict(pstatus),
        "publisher_judged": len(p_ok), "publisher_suspects": len(p_sus),
        "publisher_suspect_rate": p_rate,
        "predictions": pred, "http": dict(STATS),
        "elapsed_s": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: summary[k] for k in ("joss_works", "refs", "crossref_asserted",
                                              "suspects", "suspect_rate", "predictions")},
                     default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
