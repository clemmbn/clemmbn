"""
preview.py — renders README.md through GitHub's real markdown API and wraps
it in GitHub's CSS, to check the receipt locally before pushing.

Responsibilities
    - Sends README.md to `gh api markdown` (same sanitizer as github.com, so
      anything GitHub would strip is stripped here too).
    - Writes receipt/preview/light.html and receipt/preview/dark.html. Each
      page forces the matching <picture> source, since GitHub picks it from
      its own theme setting rather than the OS.

Constraints: needs an authenticated `gh` CLI. Serve the repo root over HTTP
(e.g. `python3 -m http.server`) so the relative SVG paths resolve.
receipt/preview/ is gitignored.
"""

import subprocess
from pathlib import Path

HERE = Path(__file__).parent
README = HERE.parent / "README.md"
CSS = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.9.0/github-markdown-{}.min.css"
BG = {"light": "#ffffff", "dark": "#0d1117"}
BORDER = {"light": "#d1d9e0", "dark": "#3d444d"}


def gh_render(md_path):
    """Return GitHub's sanitized HTML for one markdown file (raises on gh error)."""
    out = subprocess.run(
        ["gh", "api", "markdown", "-f", "mode=gfm", "-f", "context=clemmbn/clemmbn",
         "-F", f"text=@{md_path}"],
        check=True, capture_output=True, text=True,
    )
    return out.stdout


def page(body, theme):
    """Wrap rendered HTML in a profile-sized box styled like github.com."""
    # Emulate GitHub's themed-picture: force the dark source on or off
    forced = "all" if theme == "dark" else "not all"
    body = body.replace('media="(prefers-color-scheme: dark)"', f'media="{forced}"')
    # SVG paths are relative to the repo root; pages live in receipt/preview/
    body = body.replace('src="receipt/', 'src="../').replace('srcset="receipt/', 'srcset="../')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>README {theme}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="{CSS.format(theme)}">
<style>
  body {{ background:{BG[theme]}; margin:0; padding:24px 16px; }}
  .box {{ max-width:830px; margin:0 auto; border:1px solid {BORDER[theme]}; border-radius:6px; padding:24px; }}
</style></head>
<body><article class="markdown-body box">{body}</article></body></html>"""


def main():
    """Render README.md in both themes."""
    out_dir = HERE / "preview"
    out_dir.mkdir(exist_ok=True)
    html = gh_render(README)
    print(f"[preview] rendered README.md via GitHub API ({len(html)} chars)")
    for theme in BG:
        dest = out_dir / f"{theme}.html"
        dest.write_text(page(html, theme), encoding="utf-8")
        print(f"[preview]   -> {dest.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
