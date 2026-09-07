"""Render human guides with GitHub's Markdown API for a local visual review.

Requires gh authentication, development dependencies and a supported browser.
Uses GitHub's renderer with a local reading stylesheet, not GitHub's surrounding UI.
Only public documentation is submitted; no captions, audio or credentials.
"""
import argparse
import hashlib
import html
import json
import mimetypes
from pathlib import Path
import subprocess
from urllib.parse import urlsplit, unquote

from playwright.sync_api import sync_playwright
from browser_support import browser_options

ROOT = Path(__file__).resolve().parents[1]
STYLE = '''body{margin:0;background:#fff;color:#1f2328;font:16px/1.5 system-ui,sans-serif}
main{max-width:960px;margin:24px auto;padding:24px 32px;overflow-wrap:break-word}h1{font-size:2em}h1,h2{border-bottom:1px solid #d1d9e0;padding-bottom:.3em}
h2{margin-top:24px}h3{margin-top:24px}a{color:#0969da}img{max-width:100%;height:auto}pre{padding:16px;background:#f6f8fa;overflow:auto;border-radius:6px}
code{font-size:.85em;background:#eff1f3;padding:.15em .3em;border-radius:4px}pre code{padding:0;background:none}table{display:block;width:max-content;max-width:100%;overflow:auto;border-collapse:collapse;margin:16px 0}th,td{border:1px solid #d1d9e0;padding:6px 13px}tr:nth-child(2n){background:#f6f8fa}
details{margin:16px 0}summary{cursor:pointer}li+li{margin-top:4px}.anchor{display:none}blockquote{border-left:4px solid #ddd;margin-left:0;padding-left:16px;color:#59636e}
@media(max-width:600px){main{margin:0;padding:16px}h1{font-size:1.7em}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    repos = {'caption-local': ROOT, 'captionninja': ROOT/'samples/captionninja'}
    paths = [('caption-local', p.relative_to(ROOT).as_posix()) for p in sorted((ROOT/'docs').glob('*.md'))]
    paths += [('caption-local', p) for p in ['README.md', 'DEPLOYMENT.md', 'OPERATIONS.md', 'API.md', 'SECURITY.md', 'CONTRIBUTING.md']]
    paths += [('captionninja', p) for p in ['README.md', 'CAPTION-LOCAL.md', 'relay/README.md']]
    rendered = {}
    for repo, name in paths:
        source = (repos[repo]/name).read_text(encoding='utf-8')
        digest = hashlib.sha256(source.encode()).hexdigest()
        cache = args.output/(digest+'.html')
        if not cache.exists():
            output = subprocess.check_output(['gh', 'api', 'markdown', '--input', '-'],
                input=json.dumps(dict(text=source, mode='gfm', context='steveseguin/'+repo)), text=True, encoding='utf-8', timeout=45)
            cache.write_text(output, encoding='utf-8', newline='\n')
        rendered[f'/{repo}/{name}'] = f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(name)}</title><style>{STYLE}</style><main>{cache.read_text(encoding="utf-8")}</main></html>'
        print('Rendered ' + repo + '/' + name, flush=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**browser_options(), headless=True)
        try:
            context = browser.new_context()
            def serve(route):
                url = urlsplit(route.request.url)
                if url.netloc == 'localhost:8776':
                    if url.path in rendered:
                        route.fulfill(body=rendered[url.path], content_type='text/html'); return
                    parts = unquote(url.path).lstrip('/').split('/', 1)
                    if len(parts) == 2 and parts[0] in repos:
                        base = repos[parts[0]].resolve(); target = (base/parts[1]).resolve()
                        if target.is_relative_to(base) and target.is_file() and target.suffix in {'.svg', '.png', '.jpg'}:
                            route.fulfill(path=str(target), content_type=mimetypes.guess_type(target)[0]); return
                elif url.scheme == 'https' and route.request.method == 'GET' and url.hostname in {'camo.githubusercontent.com', 'user-images.githubusercontent.com', 'raw.githubusercontent.com'}:
                    route.continue_(); return
                route.fulfill(status=404, body='Not included in documentation preview')
            context.route('**/*', serve)
            context.route_web_socket('**/*', lambda ws: None)
            page = context.new_page()
            for width in (1280, 390):
                page.set_viewport_size(dict(width=width, height=900))
                for repo, name in paths:
                    page.goto(f'http://localhost:8776/{repo}/{name}')
                    slug = repo + '-' + name.replace('/', '-').removesuffix('.md') + '-' + str(width)
                    page.screenshot(path=str(args.output/(slug+'.png')), full_page=True)
                    page.screenshot(path=str(args.output/(slug+'-viewport.png')))
                    data = page.evaluate('''() => ({width:innerWidth,documentWidth:document.documentElement.scrollWidth,
                      headings:[...document.querySelectorAll('h1,h2')].map(e=>e.textContent.trim()),
                      brokenImages:[...document.images].filter(e=>!e.complete||!e.naturalWidth).map(e=>e.getAttribute('src')),
                      scrollableTables:[...document.querySelectorAll('table')].filter(e=>e.scrollWidth>e.clientWidth+1).length})''')
                    results.append(dict(repo=repo, path=name, viewport=width, **data))
            (args.output/'results.json').write_text(json.dumps(dict(scope=__doc__, browser=browser.version, pages=results), indent=2)+'\n', encoding='utf-8', newline='\n')
            print('Reviewed renders: ' + str(len(results)), flush=True)
        finally: browser.close()
    failures = [row for row in results if row['brokenImages']
                or row['documentWidth'] > row['viewport'] + 1]
    if failures:
        raise SystemExit(f'{len(failures)} guide checks failed; see {args.output / "results.json"}')


if __name__ == '__main__': main()
