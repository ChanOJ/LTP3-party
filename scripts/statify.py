#!/usr/bin/env python3
"""Statify the LTP3 (Lucky & Tigrou Party 3, 1999) event site into plain static HTML.

    python3 scripts/statify.py [--raw PATH] [--out site] [options]

Reads ONLY from the raw tree (the `party/` folder of the old server; never written to).
The event site was static HTML in a frameset, plus two things that need a server:

* the vote page (`scripts/votes.asp`, a form asking for a registration id and a birth date),
* the compo lists (`compos/*.txt`), which fed the vote form and the result page.

The vote page is replaced by `sheets/votes.html`: an "archived, read-only" notice followed by
the list of entries of each compo, rendered from `compos/*.txt` (handles and groups only; the
files are not published themselves). Everything else is copied, with the usual passes: charset
declared, e-mail redaction (none expected), font fallbacks, forms replaced by a notice.

Python 3.9+, standard library only. Files are read/written as iso-8859-1 (lossless round trip).
"""
import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ENC = "iso-8859-1"

# ---- removal-request footer: added to every page that lists or describes people
REMOVAL_MARK = 'id="removal-note"'
REMOVAL_NOTE = (
    '<div id="removal-note" style="clear:both;margin:28px auto 8px;padding:6px 8px 0;width:60%;'
    'border-top:1px solid #808080;text-align:center;font:10px/14px Verdana,Arial,Helvetica,sans-serif;'
    'color:#808080;background:transparent">To be removed from this page, '
    '<a href="mailto:chandra_oj@pm.me" style="color:#808080;text-decoration:underline">contact me</a>.</div>'
)
_BODY_END = re.compile(r"(?is)</body\s*>(?!.*</body\s*>)")


def add_removal_note(text):
    if REMOVAL_MARK in text:
        return text
    m = _BODY_END.search(text)
    if m:
        return text[: m.start()] + REMOVAL_NOTE + "\n" + text[m.start():]
    return text + "\n" + REMOVAL_NOTE + "\n"

# Pages that list or describe people (entries, jury, votes).
PEOPLE_PAGES = {"sheets/entries.html", "sheets/jury.html", "sheets/votes.html"}


def is_people_page(rel):
    return rel in PEOPLE_PAGES

REPO = Path(__file__).resolve().parent.parent
RAW_DEFAULT = Path(os.environ.get("LTP3P_RAW") or (REPO / "private" / "site-raw"))
MASK = "????"   # placeholder for every redacted value
META_CHARSET = '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
FONT = "Verdana, Arial, Helvetica, sans-serif"
# The menu linked the vote page of the old server (the file on the NAS is votes999.asp).
VOTES_OLD = "scripts/votes.asp"
VOTES_NEW = "sheets/votes.html"
COMPOS_DIR = "compos"
RENDERED = {VOTES_NEW}


class Ctx:
    def __init__(self, site, out, opts):
        self.site, self.out, self.opts = site, out, opts
        self.globs, self.excluded, self.redirects, self.warnings = [], [], [], []
        self.copied = 0
        self.compos = 0
        self.prods = 0

    def warn(self, msg):
        self.warnings.append(msg)


# --------------------------------------------------------------------------- io
def read_text(p):
    return Path(p).read_bytes().decode(ENC)


def write_text(p, s):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(s.encode(ENC, errors="xmlcharrefreplace"))


# ------------------------------------------------------------------- exclusions
def load_globs(path):
    out = []
    if path.is_file():
        for line in read_text(path).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def is_excluded(rel, globs):
    """gitignore-like: no '/' -> matches a basename anywhere; trailing '/' -> a directory;
    otherwise fnmatch on the whole path relative to site/ ('*' crosses '/')."""
    base = rel.rsplit("/", 1)[-1]
    for g in globs:
        g = g.lstrip("/")
        if g.endswith("/"):
            d = g.rstrip("/")
            if rel == d or rel.startswith(d + "/") or ("/" not in d and ("/" + d + "/") in ("/" + rel)):
                return True
        elif "/" not in g:
            if fnmatch.fnmatchcase(base, g):
                return True
        elif fnmatch.fnmatchcase(rel, g) or (g.startswith("**/") and fnmatch.fnmatchcase(rel, g[3:])):
            return True
    return False


def html_encode(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ------------------------------------------------------------------- templates
def archived_inline(what="this form"):
    return ('<P><FONT size="1" face="%s" color="#808080">'
            '[ archived: %s is no longer available &#8211; this site is a read-only snapshot ]</FONT></P>' % (FONT, what))


def render_votes(ctx):
    """sheets/votes.html: notice + the entries of each compo, in the order of the ballot
    (files A..N of compos/, one line per entry, first line = compo title)."""
    d = ctx.site / COMPOS_DIR
    files = sorted(p for p in d.glob("*.txt")) if d.is_dir() else []
    if not files:
        ctx.warn("votes: no compo list found in %s (votes.html rendered without lists)" % d)
    blocks = []
    for p in files:
        lines = read_text(p).replace("\r\n", "\n").replace("\r", "\n").split("\n")
        title, prods = lines[0].strip(), []
        for ln in lines[1:]:
            if ln.strip() == "":
                break           # the ASP stopped at the first empty line
            prods.append(ln.strip())
        rows = "".join(
            '\n  <tr bgcolor="#AA5555"><td align="right"><font face="%s" size="2">%d</font></td>'
            '<td><font face="%s" size="2">%s</font></td></tr>' % (FONT, i, FONT, html_encode(x))
            for i, x in enumerate(prods, 1))
        blocks.append(
            '<table width="60%%" border="0" align="center">\n  <tr><td bgcolor="#5E1212" colspan="2">'
            '<div align="center"><font face="%s" size="3"><b>%s</b></font> '
            '<font face="%s" size="2">(%d)</font></div></td></tr>%s\n</table>\n<p>&nbsp;</p>\n'
            % (FONT, html_encode(title), FONT, len(prods), rows))
        ctx.compos += 1
        ctx.prods += len(prods)
    return (
        '<HTML>\n<HEAD>\n<TITLE>LTP3 - Votes (archived)</TITLE>\n</HEAD>\n'
        '<BODY background="../img/fond2.gif" bgcolor="#3B1F35" text="#FFCCCC" link="#990033">\n'
        '<p><font face="%s" size="2"><b>The votes are closed.</b> During the party, each attender '
        'logged in here with a registration number and a birth date, then ranked three entries per '
        'compo. This page is now an archive: voting, registrations and the ballot are gone, only the '
        'list of the entries of each compo is kept. Every competition had a jury counting for 50%% of '
        'the votes (see <a href="jury.html">the jury</a>).</font></p>\n'
        '<p><font face="%s" size="2"><i>Les votes sont termin&eacute;s : cette page n\'est plus '
        'qu\'une archive, sans vote ni inscription.</i></font></p>\n%s\n'
        '<hr width="20%%">\n<p>&nbsp;</p>\n%s</BODY>\n</HTML>\n'
        % (FONT, FONT, archived_inline("voting"), "".join(blocks)))


# ------------------------------------------------------------ generic html pass
FORM_RE = re.compile(r"<form\b.*?</form\s*>", re.I | re.S)
ATTR_RE = re.compile(r"""(?ix)\b(href|src|background|action)\s*=\s*(?:(["'])(.*?)\2|([^\s"'>]+))""")
MAILTO_A_RE = re.compile(r"<a\b[^>]*href\s*=\s*[\"']?mailto:[^>]*>(.*?)</a\s*>", re.I | re.S)
EMAIL_RE = re.compile(r"([A-Za-z0-9._+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
FACE_VERDANA_RE = re.compile(r"""(?i)(\bface\s*=\s*)(["']?)(verdana\b[^"'>]*)(\2)""")
FONT_FALLBACK = ", DejaVu Sans, Geneva, sans-serif"


def redact_emails(text):
    text = MAILTO_A_RE.sub(lambda m: m.group(1), text)
    text = re.sub(r"(?i)mailto:", "", text)
    return EMAIL_RE.sub(lambda m: m.group(1) + "@" + MASK, text)


def add_font_fallback(text):
    def fn(m):
        value = m.group(3)
        if "sans-serif" in value.lower():
            return m.group(0)
        return m.group(1) + m.group(2) + value.rstrip() + FONT_FALLBACK + m.group(4)
    return FACE_VERDANA_RE.sub(fn, text)


def rewrite_url(u):
    """The only link to a server-side page: the vote page of the menu."""
    if u.split("#")[0].split("?")[0] == VOTES_OLD:
        return VOTES_NEW
    return u


# The pages were laid out for an 800x600 screen (frame of 637 px next to the 163 px menu). On a
# wide window the percentage widths (<hr width="20%">, tables) drift away from the text, so the
# original frameset (index.html) moves to party.html and index.html becomes a page holding it in
# a fixed 800x600 iframe, centered.
FRAMESET_OLD, FRAMESET_NEW = "index.html", "party.html"
WRAPPER = """<HTML>
<HEAD>
<TITLE>LTP3 - Make a wish</TITLE>
<style>
html, body { margin: 0; height: 100%%; background: #261422; }
body { display: flex; justify-content: center; align-items: flex-start; }
iframe { width: 800px; max-width: 100%%; height: 600px; max-height: 100vh; border: 0; }
</style>
</HEAD>
<BODY>
<IFRAME src="%s" title="LTP3 party site" frameborder="0"></IFRAME>
</BODY>
</HTML>
""" % FRAMESET_NEW


def convert_html(ctx, text):
    text = FORM_RE.sub(lambda m: archived_inline(), text)
    if not ctx.opts.keep_emails:
        text = redact_emails(text)

    def attr(m):
        val = m.group(3) if m.group(3) is not None else m.group(4)
        q = m.group(2) or ""
        return "%s=%s%s%s" % (m.group(1), q, rewrite_url(val), q)
    return add_font_fallback(ATTR_RE.sub(attr, text))


def declare_charset(text):
    if re.search(r"(?i)charset\s*=", text):
        return text
    m = re.search(r"(?i)<head[^>]*>", text) or re.search(r"(?i)<html[^>]*>", text)
    if m:
        return text[:m.end()] + "\n" + META_CHARSET + text[m.end():]
    return META_CHARSET + "\n" + text


# ------------------------------------------------------------------------- main
PAGE_EXT = (".htm", ".html", ".shtml")


def run(ctx):
    site, out = ctx.site, ctx.out
    outputs = {}
    for root, dirs, files in os.walk(site):
        dirs.sort()
        for fn in sorted(files):
            full = Path(root) / fn
            rel = full.relative_to(site).as_posix()
            if is_excluded(rel, ctx.globs):
                ctx.excluded.append(rel)
                continue
            if fn.lower().endswith(PAGE_EXT):
                if rel == FRAMESET_OLD:
                    rel = FRAMESET_NEW
                outputs[rel] = declare_charset(convert_html(ctx, read_text(full)))
                continue
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(full, dst)
            ctx.copied += 1
    outputs[FRAMESET_OLD] = declare_charset(WRAPPER)
    outputs[VOTES_NEW] = declare_charset(convert_html(ctx, render_votes(ctx)))
    ctx.redirects.append(("/" + VOTES_OLD, "/" + VOTES_NEW))
    for new_rel, text in outputs.items():
        write_text(out / new_rel, add_removal_note(text) if is_people_page(new_rel) else text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", "--raw", dest="site", default=str(RAW_DEFAULT),
                    help="raw original tree (default: $LTP3P_RAW or private/site-raw)")
    ap.add_argument("--out", default=str(REPO / "site"), help="published tree: committed and deployed (default: <repo>/site)")
    ap.add_argument("--no-clean", action="store_true", help="keep existing files in the output folder (default: it is emptied first)")
    ap.add_argument("--exclude-file", action="append", default=None,
                    help="exclusion globs file (default: scripts/exclude-globs.txt)")
    ap.add_argument("--meta-dir", default=str(REPO / "build-meta"), help="where redirects.tsv and excluded.txt are written")
    ap.add_argument("--keep-emails", action="store_true", help="do NOT redact e-mail addresses")
    opts = ap.parse_args(argv)

    site, out = Path(opts.site).resolve(), Path(opts.out).resolve()
    if not site.is_dir():
        ap.error("site folder not found: %s" % site)
    if out == site or site in out.parents or out in site.parents:
        ap.error("--out must be a separate folder, outside the source tree")
    ctx = Ctx(site, out, opts)
    for f in opts.exclude_file or [REPO / "scripts" / "exclude-globs.txt"]:
        g = load_globs(Path(f))
        if g:
            print("exclusions: %d globs from %s" % (len(g), f))
        ctx.globs += g
    if out == REPO or out in REPO.parents or (out / ".git").exists() or out in (Path.home(), Path("/")):
        ap.error("refusing to empty %s (not a dedicated output folder)" % out)
    if not opts.no_clean and out.exists():
        for _ in range(3):
            shutil.rmtree(out, ignore_errors=True)
            if not out.exists():
                break
    out.mkdir(parents=True, exist_ok=True)

    run(ctx)

    meta = Path(opts.meta_dir)
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "redirects.tsv").write_text("\n".join("%s\t%s" % r for r in ctx.redirects) + "\n", encoding="ascii", errors="replace")
    (meta / "excluded.txt").write_text("\n".join(ctx.excluded) + "\n", encoding="utf-8")
    print("rendered 1 page (votes: %d compos, %d entries); copied %d files; excluded %d"
          % (ctx.compos, ctx.prods, ctx.copied, len(ctx.excluded)))
    for w in ctx.warnings:
        print("WARNING:", w, file=sys.stderr)
    # Crawlers and frames: sitemap.xml, robots.txt and the frame-restore script tag (scripts/seo.py).
    subprocess.run([sys.executable, "-I", str(REPO / "scripts" / "seo.py"), "--site", str(out)], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
