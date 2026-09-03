"""Search Elsevier, fetch full-text XML, and convert it to the chunked markdown the extractor reads.

The extractor expects one file per paper, each a sequence of

    ID: <uuid>
    <text of that chunk>

so that an extracted value can name the chunk it came from. This turns Elsevier's article XML into
exactly that: headings, paragraphs and tables become chunks, tables keeping their shape as markdown
so a row's conditions stay with the row.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
from core.paths import data_path
from core.utils import doi_to_filename

SEARCH = "https://api.elsevier.com/content/search/sciencedirect"
SCOPUS = "https://api.elsevier.com/content/search/scopus"

# "PET" is also positron emission tomography and "glycolysis" is sugar metabolism, so a query on
# those two words alone returns oncology imaging. A title has to name the polymer AND a
# depolymerisation route to be worth fetching.
POLYMER = re.compile(r"\b(pet|poly\(?ethylene\s*terephthalate|polyethylene\s*terephthalate|"
                     r"polyester|bhet|plastic\s*waste|pet\s*bottle)", re.I)
ROUTE = re.compile(r"\b(glycolys|methanolys|hydrolys|alcoholys|solvolys|depolymeriz|depolymeris|"
                   r"chemical\s*recycl|upcycl|monomer|terephthal|dmt|bhet)", re.I)
REJECT = re.compile(r"\b(positron|tomograph|18f|fdg|psma|tumou?r|cancer|carcinoma|lymphoma|"
                    r"patient|oncolog|glioma|metabolic\s*tumou?r|enzymat|petase|cutinase|"
                    r"microplastic|a\s+review|review\s+of|systematic\s+review)", re.I)


def worth_fetching(title):
    """True when the title looks like a PET depolymerisation paper we could extract from."""
    if not title:
        return False, "no title"
    if REJECT.search(title):
        return False, "off-topic or a review"
    if not POLYMER.search(title):
        return False, "no polymer named"
    if not ROUTE.search(title):
        return False, "no depolymerisation route named"
    return True, "ok"
ARTICLE = "https://api.elsevier.com/content/article/doi"
CHUNK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "elsevier-fulltext-chunk")

# Inline elements whose text belongs to the surrounding sentence. Dropping the tag and keeping the
# text turns [P<inf>66614</inf>]-ZnO into [P66614]-ZnO rather than three fragments.
INLINE = {"inf", "sup", "italic", "bold", "underline", "monospace", "sans-serif",
          "small-caps", "glyph", "hsp", "vsp", "inter-ref", "intra-ref", "grave",
          "acute", "formula", "text", "list-item", "para", "simple-para", "label",
          "entry", "section-title", "caption", "note-para", "display", "float-anchor"}
# Elements that never carry body text worth extracting.
SKIP = {"bibliography", "reference", "ref-info", "author-group", "affiliation",
        "correspondence", "cross-ref", "cross-refs", "further-reads", "acknowledgment",
        "alt-text", "link", "objects", "scopus-id", "scopus-eid", "doi", "pii"}


def credentials():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    missing = [k for k in ("elsevier_api_key", "elsevier_inst_token") if not env.get(k)]
    if missing:
        raise SystemExit(f"missing in .env: {', '.join(missing)}")
    return {"X-ELS-APIKey": env["elsevier_api_key"],
            "X-ELS-Insttoken": env["elsevier_inst_token"]}


QUOTA = {"limit": None, "remaining": None}


def request(url, headers, accept, timeout=90, attempts=4):
    """One request, retrying throttling and transient network failures.

    A few thousand papers is long enough that a dropped connection or a burst of 429s is normal;
    without the retry the whole run dies partway and the progress is only saved per-file.
    """
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={**headers, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                head = {k.lower(): v for k, v in response.headers.items()}
                if "x-ratelimit-remaining" in head:
                    QUOTA["limit"] = head.get("x-ratelimit-limit")
                    QUOTA["remaining"] = head.get("x-ratelimit-remaining")
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                time.sleep(min(2 ** attempt * 5, 60))
                continue
            return e.code, e.read()
        except Exception as e:                                # DNS drop, reset connection
            if attempt < attempts - 1:
                time.sleep(min(2 ** attempt * 5, 60))
                continue
            return None, str(e).encode()


def search_scopus(query, wanted, headers):
    """Scopus restricts to title/abstract/keywords, so a hit is about the topic rather than merely
    mentioning it. ScienceDirect matches full text and returns ten times as many false leads."""
    dois, start = [], 0
    while len(dois) < wanted:
        url = (f"{SCOPUS}?query={urllib.parse.quote(query)}"
               f"&count={min(25, wanted - len(dois))}&start={start}&field=doi,dc:title")
        status, body = request(url, headers, "application/json")
        if status != 200:
            print(f"  scopus stopped at start={start}: HTTP {status}")
            break
        entries = json.loads(body)["search-results"].get("entry", [])
        for e in entries:
            if e.get("prism:doi"):
                dois.append((e["prism:doi"], e.get("dc:title") or ""))
        if len(entries) < 25:
            break
        start += len(entries)
        time.sleep(0.25)
    return dois


def search(query, wanted, headers):
    """DOIs for a query. ScienceDirect wants plain boolean text, not Scopus field syntax."""
    dois, start = [], 0
    while len(dois) < wanted:
        url = (f"{SEARCH}?query={urllib.parse.quote(query)}"
               f"&count={min(100, wanted - len(dois))}&start={start}")
        status, body = request(url, headers, "application/json")
        if status != 200:
            print(f"  search stopped at start={start}: HTTP {status} {body[:120]}")
            break
        entries = json.loads(body)["search-results"].get("entry", [])
        found = [e["prism:doi"] for e in entries if e.get("prism:doi")]
        if not found:
            break
        dois += found
        start += len(entries)
        time.sleep(0.2)
    return list(dict.fromkeys(dois))[:wanted]


def name_of(element):
    return etree.QName(element).localname


def flatten(element):
    """All text under an element, with inline markup dissolved into the sentence."""
    pieces = []
    if element.text:
        pieces.append(element.text)
    for child in element:
        if name_of(child) in SKIP:
            if child.tail:
                pieces.append(child.tail)
            continue
        pieces.append(flatten(child))
        if child.tail:
            pieces.append(child.tail)
    return "".join(pieces)


def tidy(text):
    return re.sub(r"[ \t ]+", " ", (text or "").replace("\n", " ")).strip()


def table_to_markdown(table):
    """A CALS table as a markdown table, so each row's values stay on one line."""
    caption = ""
    for child in table.iter():
        if name_of(child) in ("caption", "simple-para") and not caption:
            caption = tidy(flatten(child))
    label = ""
    for child in table:
        if name_of(child) == "label":
            label = tidy(flatten(child))
            break

    rows = []
    for row in table.iter():
        if name_of(row) != "row":
            continue
        cells = [tidy(flatten(cell)) for cell in row if name_of(cell) == "entry"]
        if any(cells):
            rows.append(cells)
    if not rows:
        return None

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, body = rows[0], rows[1:]
    lines = [f"| {' | '.join(header)} |", "|" + "|".join([" --- "] * width) + "|"]
    lines += [f"| {' | '.join(r)} |" for r in body]
    heading = " ".join(x for x in (label, caption) if x)
    return (heading + "\n" if heading else "") + "\n".join(lines)


def blocks_from(article, coredata):
    """Ordered text blocks: title, abstract, then every heading, paragraph and table."""
    out = []
    title = coredata.get("title")
    if title:
        out.append(title)
    abstract = coredata.get("abstract")
    if abstract:
        out.append("Abstract\n" + abstract)

    seen_tables = set()
    for element in article.iter():
        tag = name_of(element)
        if tag == "section-title":
            text = tidy(flatten(element))
            if text:
                out.append("## " + text)
        elif tag in ("para", "simple-para"):
            if any(name_of(a) in ("para", "simple-para") for a in element.iterancestors()):
                continue                                       # nested, already covered
            if any(name_of(a) == "table" for a in element.iterancestors()):
                continue                                       # belongs to a table
            text = tidy(flatten(element))
            if len(text) > 1:
                out.append(text)
        elif tag == "table" and id(element) not in seen_tables:
            seen_tables.add(id(element))
            rendered = table_to_markdown(element)
            if rendered:
                out.append(rendered)
    return out


def split_long(text, limit=2800):
    """Keep chunks reviewable. Tables are never split; a row must stay with its header."""
    if len(text) <= limit or text.lstrip().startswith("|") or "\n| " in text:
        return [text]
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if current and len(current) + len(sentence) + 1 > limit:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def to_markdown(xml_bytes, doi):
    root = etree.fromstring(xml_bytes)
    core = {}
    for element in root.iter():
        tag = name_of(element)
        if tag == "title" and "title" not in core and element.text:
            core["title"] = tidy(element.text)
        elif tag == "description" and "abstract" not in core:
            core["abstract"] = tidy(flatten(element))
        if len(core) == 2:
            break

    original = None
    for element in root.iter():
        if name_of(element) == "originalText":
            original = element
            break
    if original is None:
        return None, 0

    blocks = []
    for block in blocks_from(original, core):
        blocks.extend(split_long(block))

    lines = []
    for position, block in enumerate(blocks):
        key = f"{doi}#{position}#{block[:200]}"
        lines.append(f"ID: {uuid.uuid5(CHUNK_NAMESPACE, key)}\n{block}\n")
    return "\n".join(lines), len(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", action="append", default=None,
                    help="repeatable; Scopus TITLE-ABS-KEY syntax when --source scopus")
    ap.add_argument("--source", choices=["scopus", "sciencedirect"], default="scopus")
    ap.add_argument("--limit", type=int, default=25, help="max papers per query")
    ap.add_argument("--out", default="mass_markdown_by_doi",
                    help="directory under artifacts/data to write into")
    ap.add_argument("--dois", nargs="*", help="fetch these DOIs instead of searching")
    ap.add_argument("--dois-from", help="CSV from cli/harvest_corpus.py; fetches the rows it kept")
    args = ap.parse_args()

    headers = credentials()
    out_dir = data_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dois_from:
        import csv as _csv
        with data_path(args.dois_from).open(encoding="utf-8") as fh:
            rows = list(_csv.DictReader(fh))
        dois = [r["doi"] for r in rows if r["keep"].lower() == "true"]
        print(f"  {len(rows)} candidates in {args.dois_from}, {len(dois)} passed the filter")
    elif args.dois:
        dois = args.dois
    else:
        finder = search_scopus if args.source == "scopus" else search
        found_all = []
        for query in (args.query or ['TITLE-ABS-KEY(PET AND glycolysis AND catalyst)']):
            found = finder(query, args.limit, headers)
            print(f"  {len(found):5d} hits: {query}")
            found_all += found

        seen, candidates, rejected = set(), [], {}
        for doi, title in found_all:
            if doi in seen:
                continue
            seen.add(doi)
            keep, why = worth_fetching(title)
            if keep:
                candidates.append(doi)
            else:
                rejected[why] = rejected.get(why, 0) + 1
        dois = candidates
        print(f"\n  {len(seen)} unique DOIs")
        for why, n in sorted(rejected.items(), key=lambda kv: -kv[1]):
            print(f"    dropped {n:5d}  {why}")
        print(f"  {len(dois)} worth fetching\n")
    print(f"{len(dois)} papers to fetch -> {out_dir}\n")

    written, skipped, failed = 0, 0, []
    index = []
    for doi in dois:
        target = out_dir / doi_to_filename(doi, "md")
        if target.exists():
            skipped += 1
            continue
        status, body = request(f"{ARTICLE}/{doi}?view=FULL", headers, "text/xml")
        if status != 200:
            failed.append((doi, status))
            continue
        try:
            markdown, chunks = to_markdown(body, doi)
        except Exception as e:
            failed.append((doi, f"parse: {e}"))
            continue
        if not markdown or chunks < 5:
            failed.append((doi, f"only {chunks} chunks"))
            continue
        target.write_text(markdown, encoding="utf-8")
        index.append({"doi": doi, "chunks": chunks, "chars": len(markdown)})
        written += 1
        print(f"  {doi:42s} {chunks:4d} chunks  {len(markdown)//1024:4d} KB")
        time.sleep(0.2)

    (out_dir / "_index.json").write_text(json.dumps(index, indent=2))
    print(f"\nwritten {written} | already present {skipped} | failed {len(failed)}")
    if QUOTA["remaining"]:
        print(f"Elsevier quota: {QUOTA['remaining']} of {QUOTA['limit']} requests left this week")
    reasons = {}
    for _, why in failed:
        key = str(why).split(":")[0][:40]
        reasons[key] = reasons.get(key, 0) + 1
    for key, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {key}")
    for doi, why in failed[:10]:
        print(f"  FAILED {doi}: {why}")


if __name__ == "__main__":
    main()
