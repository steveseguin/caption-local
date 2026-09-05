"""Check source syntax, local documentation links and public-release hygiene."""
import ast
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
roots = ['docs', 'skills', 'scripts', 'tests', 'static', 'evidence', '.github']
files = [p for p in root.iterdir() if p.is_file() and p.name != '.env']
for name in roots:
    files.extend(p for p in (root/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
errors = []
for path in files:
    if path.suffix == '.py':
        ast.parse(path.read_text(), filename=str(path))
    if path.suffix not in {'.md', '.py', '.js', '.json', '.yaml', '.yml', '.txt', '.sh', '.ps1', '.log'}:
        continue
    text = path.read_text()
    for pattern in [r'gh[pousr]_[A-Za-z0-9]{30,}', r'hf_[A-Za-z0-9]{30,}',
                    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']:
        if re.search(pattern, text):
            errors.append(f'Possible credential: {path.relative_to(root)}')
    if path.suffix != '.md':
        continue
    for target in re.findall(r'\]\(([^\s)]+)(?:\s+[^)]*)?\)', text):
        if target.startswith(('https://', 'http://', '#', 'mailto:')):
            continue
        target = target.split('#')[0]
        if target and not (path.parent/target).exists():
            errors.append(f'Broken local link: {path.relative_to(root)} -> {target}')
version = (root/'VERSION').read_text().strip()
server = ast.parse((root/'server.py').read_text())
values = {n.targets[0].id: n.value.value for n in server.body
          if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
assert values['VERSION'] == version, 'VERSION and server.py disagree'
assert (root/'LICENSE').read_text().startswith('Mozilla Public License'), 'Expected MPL license'
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Release checks passed: {version}; {len(files)} source/documentation/evidence files inspected.')
