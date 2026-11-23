# LTP3-party

**Lucky & Tigrou Party 3 (1999), the event website.** LTP was a French demoparty series. This is
the site that ran *during* the LTP3 party: news, practical information, planning, network
settings, jury, the entries of every compo (in order of appearance), the fast compo subjects and
the vote page. The public website of LTP3 (invitation, rules, registration, results) is a
separate archive.

Archive of an old website (static HTML in a frameset, one classic-ASP vote page), published as a
**100 % static, read-only site** on bunny.net at the hostname of [`site.json`](site.json).
Kept online for history, no longer developed. Visitors can never write anything: the pages are
the cleaned static pages committed in `site/`, the CDN only serves files, and every method
except GET/HEAD/OPTIONS is refused at the edge.

## Layout

| Path | Content |
| --- | --- |
| `site/` | The cleaned static site, exactly as served |
| `private/` | Raw original (git-ignored, never published): `site-raw/` (the `party/` folder of the old server) |
| `hosting/404.html` | Custom 404 page, deployed next to `site/` |
| `site.json` | The only site-specific settings: repository, storage zone, pull zone, hostname, 404 page |
| `infra/` | OpenTofu: storage zone, pull zone, hostname, hardening edge rules (state encrypted, committed) |
| `infra/secrets.env` | Proton Pass **references** to the secrets (vault `OldSites`), no secret values |
| `scripts/statify.py` | Raw original (`private/`) → cleaned `site/` (run locally) |
| `scripts/verify_build.py` | Checks `site/`: no ASP/SSI, forms, e-mails, credentials, new broken links |
| `scripts/check_excludes.py` | Fails if `site/` holds a path of `scripts/exclude-globs.txt` |
| `scripts/preview.py` | Local preview with the charsets of the edge rules |
| `scripts/deploy.py` | Sync `site/` to the storage zone, purge the CDN |
| `scripts/smoke_test.py` | Check the public site: pages as in `site/`, POST refused, security headers, charset, 404 |
| `scripts/bootstrap.sh` | One-time setup (`new` for this site, `github` for the repository and secrets) |

DNS is not managed here: the hostname is a CNAME to `<pull zone>.b-cdn.net` at Infomaniak.

## What was changed from the original

Source: `Sites web/ltp3/party/` on the NAS (44 files), copied into `private/site-raw/`.

- **Pages kept as they were**: `menu.html`, `sheets/` (`news`, `infos`, `planning`, `network`,
  `entries`, `jury`, `fastcompos`, `contact`) and `img/`: same names, same content. Only the
  charset is declared in the HTML pages and `face="Verdana"` gets sans-serif fallbacks
  (`DejaVu Sans, Geneva, sans-serif`) for systems without Verdana.
- **Frameset in an iframe**: the pages were laid out for an 800x600 screen, and on a wide window the
  percentage widths (`<hr width="20%">`, tables) drift away from the text. The original frameset
  moved from `index.html` to `party.html`, and `index.html` is a new page showing it in a fixed
  800x600 iframe, centered (`WRAPPER` in `scripts/statify.py`).
- **Vote page replaced**: the menu pointed to `scripts/votes.asp`, a form asking for a registration
  number and a birth date, then recording three ranked choices per compo. It is now
  `sheets/votes.html` (`build-meta/redirects.tsv` lists the old → new name): an "archived,
  read-only" notice and the list of entries of each of the 14 compos (156 entries: handles and
  groups only), rendered from the compo files that fed the ballot.
- **Results**: the party results were computed from a database (votes, jury weights) that is not
  part of the event site, and the votes themselves are personal: there is no results page here.
- **Not published** (`scripts/exclude-globs.txt`): the ASP source (`scripts/votes999.asp`), the
  raw compo files (`compos/*.txt`, rendered into the vote page), `.DS_Store`. Never copied
  to `private/` or published: the organisers' pages (registration, jury draw, search,
  results: they hold registrations and real names), the database import scripts
  (`csv2sql_*.vbs`), `votes.bak` (a backup of the vote page source), `ltpdata/` (logins, forum), shell
  dotfiles of the old server (`.bash*`, `.Xdefaults`, `.inputrc`) and the public website
  (`http/`, `secure/`).
- **Left as they were**: handles and groups as listed on the entries and jury pages (no real
  names or contact details anywhere), the party LAN settings of `network.html` (private
  192.168.x.x addresses), the wording and typos of the pages.

## Regenerating `site/`

`site/` is generated: never edit it by hand, fix `scripts/statify.py` and regenerate. The raw
original lives in `private/` (git-ignored; `$LTP3P_RAW` overrides the path); the build never
reads the NAS. Keep `private/`, it is the working copy.

```bash
python3 scripts/statify.py && python3 scripts/verify_build.py && python3 scripts/check_excludes.py
```

```bash
python3 scripts/preview.py 3871
```

## Hardening (`infra/main.tf`)

- Edge rule 1: any method other than GET, HEAD, OPTIONS is blocked at the edge, before the
  origin (bunny.net answers 403; edge rules cannot return 405). `block_post_requests` is also on.
- Edge rule 2: `Content-Security-Policy` (same-origin, inline script/style allowed, images from
  the site only, `form-action 'none'`), `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`, HSTS, `Permissions-Policy`.
- Edge rules 3-4: `Content-Type` with `charset=iso-8859-1` for `.htm/.html/.shtml/.SHTML` and
  `.txt/.c` (the pages are ISO-8859-1).
- Edge rule 5: browser cache 7 days for images and archives, 1 hour for pages; CDN cache 30
  days, purged on each deployment.
- Archives (`zip swf`): `application/octet-stream` + `Content-Disposition: attachment` (none in this site).
- COOP/CORP `same-origin`. Search engines are allowed (no `X-Robots-Tag`, no `robots.txt`).
- CI (deploy workflow), before upload: excluded-paths check, `scripts/verify_build.py --build site`
  and a ClamAV scan of `site/`.
- Cookies are stripped before the origin; TLS "Compatible"; forced HTTPS.
- Custom 404: `hosting/404.html` (`not_found_page` in `site.json`).

## Removal requests

Pages that list or describe people end with a small footer, "To be removed from this page, contact me." (a `mailto:` link). `scripts/statify.py` adds it (`is_people_page`), so it survives rebuilds; `scripts/verify_build.py` leaves it out of its `mailto:` and e-mail checks.

## Deploying

- **Website**: push a change under `site/` or `hosting/` to `main` → workflow *Website: deploy*
  runs the checks, uploads the changed files, deletes the removed ones, purges the CDN and
  runs the smoke test. A manual run allows a dry run.
- **Infra**: pull requests touching `infra/` show the plan; apply is a manual run of
  *Infra: bunny.net* (action `apply`, from `main`), which commits the encrypted state, deploys
  `site/` and runs the smoke test.

GitHub secrets: `BUNNY_API_KEY` (bunny.net account API key) and `TF_VAR_STATE_PASSPHRASE`
(state encryption), both from Proton Pass vault `OldSites`.

Locally (Proton Pass CLI logged in):

```bash
pass-cli run --env-file infra/secrets.env -- python3 scripts/deploy.py --dry-run
```

```bash
cd infra && pass-cli run --env-file secrets.env -- tofu plan
```

## First setup (done on 2026-11-23, kept as a record)

1. Write `site.json` and validate offline (done on 2026-11-23; secrets are the shared ones of
   the other old sites: same Proton Pass references):

   ```bash
   scripts/bootstrap.sh new LTP3-party ltp3-party ltp3-party ltp3-party.sauthier.family
   ```

2. Create the GitHub repository and its secrets, push, open the PR (done on 2026-11-23):

   ```bash
   scripts/bootstrap.sh github
   ```

3. After merge, run the *Infra: bunny.net* workflow with action `apply` (done on 2026-11-23): it creates the zones,
   hostname and edge rules, deploys `site/` and runs the smoke test.
4. At Infomaniak (Manager > Domaines > sauthier.family > Zone DNS), add a CNAME (done on 2026-11-23)
   `ltp3-party` → `ltp3-party.b-cdn.net`. The certificate is issued once DNS answers;
   re-run the smoke test (*Monitoring: weekly smoke test*, manual run) after a few minutes.

## Manual steps in the bunny.net dashboard (only if the apply cannot do it)

If the apply rejects an edge rule or the 404 path, set it by hand (CDN > pull zone
`ltp3-party`):

1. *Edge rules* > *Add Edge Rule*: condition *Request Method* is none of `GET`, `HEAD`,
   `OPTIONS` → action *Block Request*.
2. *Edge rules* > *Add Edge Rule*: condition *URL* `*` → one *Set Response Header* action per
   header listed above (values in `infra/main.tf`, `local.csp` and the rule 2 block).
3. *Edge rules*: condition *URL Extension* `htm`, `html`, `shtml`, `SHTML` → *Set Response Header*
   `Content-Type: text/html; charset=iso-8859-1`.
4. Storage > storage zone `ltp3-party` > *Error pages*: set the 404 file to `/404.html`.
