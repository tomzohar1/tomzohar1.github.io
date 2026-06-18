# Project Memory — tomzohar.com

## ⚠️ CRITICAL: Git / Push Workflow

### The Problem
The local repo lives inside **Dropbox**, which corrupts git object files (empty blob errors like `fatal: loose object ... is empty`). This means:
- `git push` from the Dropbox repo fails silently or with corrupt-object errors
- `git pull` also fails — new remote commits can't be fetched
- GitHub Desktop gets stuck showing "unable to pull when there are changes on your branch"

### The Fix (in order of preference)
1. **GitHub API** (fastest for small files like index.html, .tex):
   ```bash
   SHA=$(gh api repos/tomzohar1/tomzohar1.github.io/contents/PATH --jq '.sha')
   B64=$(base64 -i FILE | tr -d '\n')
   gh api --method PUT repos/tomzohar1/tomzohar1.github.io/contents/PATH \
     -f message="commit message" -f content="$B64" -f sha="$SHA" --jq '.commit.sha'
   ```
2. **Temp clone** (needed for large files like PDFs):
   ```bash
   git clone --depth 1 https://github.com/tomzohar1/tomzohar1.github.io.git /tmp/tzfix
   # copy changed files in, then commit and push from /tmp/tzfix
   ```
   ⚠️ Shallow clones of this repo are SLOW (large PDF assets) — allow 2–3 minutes.

3. **Never** try to push from the Dropbox repo directly.

### Fixing GitHub Desktop conflicts
When Desktop shows "unable to pull — changes on your branch":
```bash
cd "/Users/tomzohar/CEMFI Dropbox/tom zohar/Tools/website/tomzohar1.github.io"
find .git/objects -type f -empty -delete
git checkout -- <modified files>   # discard local changes (already on remote)
git pull origin master
```
If pull still says "Already up to date" despite being behind, the .git is too corrupt —
replace it: copy `.git` from a fresh `/tmp/tzfix` clone into the Dropbox folder.

---

## ⚠️ jQuery 3 Compatibility

When jQuery was upgraded from 2.x → 3.x (now at 3.7.1), two deprecated APIs were
removed that broke the site's JavaScript:

| File | Old API | Replacement |
|------|---------|-------------|
| `assets/js/main.js` | `$(window).load(fn)` | `$(window).on('load', fn)` |
| `assets/plugins/nivo-lightbox/nivo-lightbox.js` | `img.load(fn)` / `img.error(fn)` | `img.on('load', fn)` / `img.on('error', fn)` |
| `assets/plugins/nivo-lightbox/nivo-lightbox.min.js` | same | same |

Fix commit: `75bc07c`. If the site ever breaks after a jQuery update, check these files first.

---

## Working Paper Series — Submission Portals

Tom is a member of:
- **CESifo**: submit at https://www.cesifo.org/en/form/working-paper-upload-preselect
- **RFBerlin (Rockwool Foundation Berlin)**: no public portal — contact directly

---

## Website Structure

- Single-page site: `index.html` (all content)
- Custom styles: `assets/css/custom.css`
- CV source: `assets/cv/cv_TomZohar.tex` → compile → `cv_TomZohar.pdf` + `Tom Zohar - CV.pdf`
- Compile CV: `cd assets/cv && pdflatex cv_TomZohar.tex && cp cv_TomZohar.pdf "Tom Zohar - CV.pdf"`
- Push via GitHub API (see above) — do NOT push PDFs from Dropbox repo

## Section order (index.html)
1. Publications (forthcoming/conditionally accepted)
2. Working Papers (ordered by journal prestige / R&R status first)
3. Selected Work in Progress
4. Policy Reports

## Working paper series links style
Match the pattern used for existing papers (e.g. Firms IGM → CESifo):
```html
<h4 class="c-work__title">
    <a href="URL" target="_blank">CESifo Working Paper</a>
</h4>
```
