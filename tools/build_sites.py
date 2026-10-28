"""Generate the Franklin site's pages (sites/franklin/*.md) from the files in data/.

    data/papers.yaml        -> publications
    data/teaching.yaml      -> courses
    data/group.yaml         -> students
    data/media.yaml         -> media mentions and news
    data/updates.yaml       -> "Updates" on the home page (+ /updates/ archive)
    data/outreach.md        -> CalMentors (plain Markdown)
    data/miscellaneous.md   -> Miscellaneous (plain Markdown)

Usage (from the Website/ folder):
    python3 tools/build_sites.py

The generated pages are overwritten each time, so edit the files in data/, not
the .md files in sites/franklin/.
"""

import html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FRANKLIN = ROOT / "sites" / "franklin"
ME = "Gireeja Ranade"


def load(name):
    with (DATA / name).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def write(path: Path, text: str, overwrite=True):
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def bold_me(authors, fmt="md"):
    if fmt == "md":
        return authors.replace(ME, f"**{ME}**")
    return html.escape(authors).replace(ME, f"<strong>{ME}</strong>")


# --------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------

def person_md(s):
    name = f"[{s['name']}]({s['url']})" if s.get("url") else s["name"]
    out = f"+ {name}"
    if s.get("role"):
        out += f" ({s['role']})"
    if s.get("note"):
        note = f"[{s['note']}]({s['note_url']})" if s.get("note_url") else s["note"]
        out += f". {note}"
    return out


def group_md(g):
    """Render data/group.yaml. The `to_confirm` list is deliberately not rendered."""
    lines = [g["intro"], "", "## PhD students", ""]
    for s in g.get("phd", []):
        role = f"co-advised with {s['coadvisor']}" if s.get("coadvisor") else ""
        lines.append(person_md({**s, "role": role}))
    if g.get("undergrad"):
        lines += ["", "## Undergraduate researchers", ""]
        lines += [person_md({**s, "role": s.get("project", "")}) for s in g["undergrad"]]
    lines += ["", "## Alumni", ""]
    lines += [person_md(s) for s in g.get("alumni", [])]
    return "\n".join(lines) + "\n"


def talks_md(talks):
    return "\n".join(f"+ [{t['title']}]({t['url']}), {t['venue']}, {t['date']}" for t in talks) + "\n"


# --------------------------------------------------------------------------
# Franklin (just-the-docs template, as used on franklinjl.org)
# --------------------------------------------------------------------------

def fr_paper(p):
    title = html.escape(p["title"])
    t = f'<a href="{html.escape(p["url"])}">{title}</a>' if p["url"] else title
    venue = f'<div class="pub-venue">{html.escape(p["venue"])}</div>' if p["venue"] else ""
    note = f'<div class="pub-note">{html.escape(p["note"])}</div>' if p.get("note") else ""
    return (f'<li class="pub"><div class="pub-title">{t}</div>'
            f'<div class="pub-authors">{bold_me(p["authors"], "html")}</div>{venue}{note}</li>')


def fr_list(items):
    return "~~~\n<ul class=\"pub-list\">\n" + "\n".join(fr_paper(p) for p in items) + "\n</ul>\n~~~\n"


# --- Updates (news) -------------------------------------------------------

HOME_UPDATES = 8  # number of updates shown on the home page; the rest go to /updates/
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def update_key(u):
    """Sort key from `date` (YYYY, YYYY-MM or YYYY-MM-DD); missing parts count as 0."""
    parts = [int(x) for x in str(u["date"]).split("-")]
    return tuple(parts + [0] * (3 - len(parts)))


def update_label(u):
    if u.get("label"):
        return u["label"]
    y, m, _ = update_key(u)
    return f"{MONTHS[m - 1]} {y}" if m else str(y)


def inline_md(s):
    """Tiny Markdown -> HTML for update text: [links](url), **bold**, *italic*."""
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def fr_updates(items):
    rows = "\n".join(
        f'<li><span class="update-date">{html.escape(update_label(u))}</span>'
        f'<span class="update-text">{inline_md(u["text"])}</span></li>'
        for u in items)
    return f'~~~\n<ul class="updates">\n{rows}\n</ul>\n~~~\n'


# --- Teaching -------------------------------------------------------------

def a(text, url=None):
    text = html.escape(text)
    return f'<a href="{html.escape(url)}">{text}</a>' if url else text


def fr_course(c):
    rows = [f'<div class="course-title">{a(c["code"] + ": " + c["title"], c.get("url"))}</div>']
    if c.get("role"):
        rows.append(f'<div class="course-role">{html.escape(c["role"])}</div>')
    sems = ", ".join(a(s["term"], s.get("url")) for s in c.get("semesters") or [])
    if sems:
        rows.append(f'<div class="course-terms">{sems}</div>')
    links = " · ".join(a(l["text"], l["url"]) for l in c.get("links") or [])
    if links:
        rows.append(f'<div class="course-links">{links}</div>')
    if c.get("note"):
        rows.append(f'<div class="pub-note">{html.escape(c["note"])}</div>')
    return '<li class="pub course">' + "".join(rows) + "</li>"


def fr_courses(courses):
    return '~~~\n<ul class="pub-list course-list">\n' + "\n".join(fr_course(c) for c in courses) + "\n</ul>\n~~~\n"


def build_franklin(papers, teaching, group, media, outreach, miscellaneous, updates):
    f = FRANKLIN
    updates = sorted(updates or [], key=update_key, reverse=True)  # stable: ties keep file order
    recent, older = updates[:HOME_UPDATES], updates[HOME_UPDATES:]
    updates_home = ""
    if recent:
        updates_home = "## Updates\n\n" + fr_updates(recent)
        if older:
            updates_home += "\n[Older updates →](/updates/)\n"
    # --- Home / About
    write(f / "index.md", """@def title = "Gireeja Ranade"
@def tags = ["about"]

~~~
<div class="profile">
  <img class="profile-photo" src="/assets/gireeja.png" alt="Photo of Gireeja Ranade">
  <div class="profile-info">
    <h1 class="profile-name">Gireeja Ranade</h1>
    <p class="profile-contact">
      <a href="mailto:ranade@eecs.berkeley.edu">ranade@eecs.berkeley.edu</a><br>
      Gateway 4443, Berkeley CA 94720<br>
      <a href="https://scholar.google.com/citations?user=XBjhKdoAAAAJ">Google Scholar</a>
    </p>
  </div>
</div>
~~~

## Bio

Gireeja Ranade is an Associate Teaching Professor in the Electrical Engineering and Computer Science Department at UC Berkeley. Her research interests span theoretical projects in machine learning and control, AI for Math, and societal impacts of AI and education. She teaches upper-division and graduate level courses such as deep learning and optimization, as well as introductory undergraduate courses. Before joining the faculty at UC Berkeley, Prof. Ranade was a Researcher at [Microsoft Research AI](https://www.microsoft.com/en-us/research/lab/microsoft-research-ai/) in the [Adaptive Systems and Interaction Group](https://www.microsoft.com/en-us/research/group/adaptive-systems-and-interaction/). She also designed and taught the first offering for the new course sequence [EECS16A](https://inst.eecs.berkeley.edu/~ee16a/sp15) and [EECS16B](https://inst.eecs.berkeley.edu/~ee16b/fa15) in the EECS department at UC Berkeley and received the 2017 UC Berkeley Electrical Engineering Award for Outstanding Teaching. She was also awarded the 2020 UC Berkeley award for Extraordinary Teaching in Extraordinary Times. Prof. Ranade received her PhD in [Electrical Engineering and Computer Science](https://eecs.berkeley.edu/) from the [University of California, Berkeley](https://berkeley.edu/), and her undergraduate degree from [MIT](https://web.mit.edu/) in Cambridge, MA.

""" + updates_home)

    # --- Older updates (everything not shown on the home page)
    write(f / "updates.md", "\n".join([
        '@def title = "Older updates"\n',
        "# Older updates\n",
        "<!-- Generated from data/updates.yaml - edit that file, not this one. -->\n",
        fr_updates(older) if older else "No older updates yet.\n",
        "Back to [recent updates](/).\n",
    ]))

    # --- Papers: one reverse-chronological list (ties keep the order in papers.yaml)
    by_year = sorted(papers, key=lambda p: p.get("year") or 0, reverse=True)
    parts = ['@def title = "Papers"\n',
             "# Papers\n",
             "<!-- Generated from data/papers.yaml - edit that file, not this one. -->\n",
             "I am thankful for the many wonderful collaborations that have led to the publications here. "
             "A more exhaustive list is at [Google Scholar](https://scholar.google.com/citations?user=XBjhKdoAAAAJ).\n",
             fr_list(by_year)]
    write(f / "papers.md", "\n".join(parts))

    # --- Teaching: one flat list of courses, plus "As a graduate student"
    parts = ['@def title = "Teaching"\n', "# Teaching\n",
             "<!-- Generated from data/teaching.yaml - edit that file, not this one. -->\n",
             fr_courses(teaching.get("courses", []))]
    if teaching.get("grad_student"):
        parts += ["## As a graduate student\n", fr_courses(teaching["grad_student"])]
    write(f / "teaching.md", "\n".join(parts))

    # --- Group, media, outreach, miscellaneous
    write(f / "group.md", '@def title = "Group"\n\n# Group\n\n@@compact\n'
          + group_md(group).replace("\n+ ", "\n* ") + "@@\n")
    media_header = (
        '@def title = "Media"\n\n'
        '# Media\n\n'
        '<!--\n'
        '  To add a new item, add a bullet at the top of this list (or in data/media.yaml):\n'
        '  * [Title](https://...), Outlet, Month Year\n'
        '-->\n\n'
    )
    write(f / "media.md", media_header + talks_md(media).replace("+ ", "* "))
    write(f / "outreach.md", '@def title = "Outreach"\n\n# Outreach\n\n' + outreach)
    write(f / "miscellaneous.md", '@def title = "Miscellaneous"\n\n# Miscellaneous\n\n' + miscellaneous)
    print(f"Franklin: regenerated index ({len(recent)} updates), updates ({len(older)} older), "
          "papers, teaching, group, media, outreach, miscellaneous")


def main():
    papers = load("papers.yaml")
    teaching = load("teaching.yaml")
    group = load("group.yaml")
    media = load("media.yaml")
    outreach = (DATA / "outreach.md").read_text(encoding="utf-8")
    miscellaneous = (DATA / "miscellaneous.md").read_text(encoding="utf-8")
    updates = load("updates.yaml") if (DATA / "updates.yaml").exists() else []

    build_franklin(papers, teaching, group, media, outreach, miscellaneous, updates)


if __name__ == "__main__":
    main()
