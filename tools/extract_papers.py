"""Extract the publication list from the original index.html into papers.yaml.

The original site lists papers inside `.row` blocks (one per topic) that each
contain an <h4> heading and several `.paper-item` entries. The same paper can
appear in several rows (e.g. "Selected" and a topic row), so entries are
de-duplicated by normalised title and their topics merged.

Usage: python3 tools/extract_papers.py  (run from the Website/ folder)
"""

import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "index.html"
OUT = ROOT / "data" / "papers.yaml"

# Map the original <h4> headings onto short topic tags.
TOPIC_MAP = {
    "Selected Publications/Preprints": "selected",
    "Other recent works": "recent",
    "Understanding Misinformation": "Misinformation",
    "Information and control theory": "Information and control theory",
    "Protocol design for wireless control": "Wireless control",
    "Safety and Control": "Safety and control",
    "Crowdsourcing": "Crowdsourcing",
    "Programmable optical networks for datacenters": "Datacenter networks",
    "Neuroscience and brain-machine interfaces": "Neuroscience",
    "Cardiovascular Modeling and Prediction": "Cardiovascular modeling",
    "Theses": "Theses",
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def norm_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def slugify(title: str, year) -> str:
    words = re.sub(r"[^a-z0-9 ]", "", title.lower()).split()
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "is", "there"}
    words = [w for w in words if w not in stop][:5]
    return "-".join(words) + (f"-{year}" if year else "")


def main():
    html = SRC.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    # Drop commented-out markup so disabled entries (e.g. Economics) are skipped.
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    papers: dict[str, dict] = {}
    order = 0
    topic = None

    # The original markup has unbalanced tags, so rather than relying on the
    # DOM nesting we walk elements in document order and remember the most
    # recent <h4>. We stop at the Teaching <h3> (courses reuse .paper-item).
    for el in soup.find_all(["h3", "h4", "div"]):
        if el.name == "h3" and "Teaching" in el.get_text():
            break
        if el.name == "h4":
            heading = clean(el.get_text())
            topic = TOPIC_MAP.get(heading, heading)
            continue
        if el.name != "div" or "paper-item" not in (el.get("class") or []) or topic is None:
            continue
        item = el
        if True:
            title_el = item.select_one(".paper-title")
            if not title_el:
                continue
            title = clean(title_el.get_text())
            authors_el = item.select_one(".paper-author")
            venue_el = item.select_one(".paper-type")
            link = item.find("a")
            note_el = item.find("font")

            # Venue may contain <br> separating multiple venues.
            venue = ""
            if venue_el:
                for br in venue_el.find_all("br"):
                    br.replace_with("|||")
                venue = "; ".join(
                    clean(s) for s in venue_el.get_text().split("|||") if clean(s)
                )
            authors = clean(authors_el.get_text()) if authors_el else "Gireeja Ranade"
            years = re.findall(r"(?:19|20)\d{2}", venue)
            year = int(max(years)) if years else None

            # Same title + same year => same paper (listed under several
            # headings). Different years => e.g. conference vs journal version.
            key = norm_key(title) + "|" + str(year or "")
            if year is None:
                # Attach to an existing entry with this title if there is one.
                key = next((k for k in papers if k.startswith(norm_key(title) + "|")), key)
            if key not in papers:
                order += 1
                papers[key] = {
                    "title": title,
                    "authors": authors,
                    "venue": venue,
                    "year": year,
                    "url": link["href"].strip() if link and link.has_attr("href") else "",
                    "note": clean(note_el.get_text()) if note_el else "",
                    "topics": [],
                    "selected": False,
                    "order": order,
                }
            p = papers[key]
            if topic == "selected":
                p["selected"] = True
            elif topic == "recent":
                p.setdefault("recent", True)
            elif topic not in p["topics"]:
                p["topics"].append(topic)
            # Prefer the more informative venue string / a year if missing.
            if len(venue) > len(p["venue"]):
                p["venue"] = venue
                p["year"] = year or p["year"]

    out = []
    for p in sorted(papers.values(), key=lambda p: p["order"]):
        p.pop("order")
        if p.pop("recent", False) and not p["topics"]:
            p["topics"].append("Recent work")
        p["id"] = slugify(p["title"], p["year"])
        out.append(p)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("# Publications extracted from the original website.\n")
        f.write("# Edit this file to add/remove papers; both site generators read from it.\n")
        yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, width=100)
    print(f"Wrote {len(out)} papers to {OUT}")


if __name__ == "__main__":
    main()
