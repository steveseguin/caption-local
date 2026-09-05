"""Build a source release with an explicit allowlist; exclude models/audio/secrets."""
import gzip
import hashlib
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
version = (root/'VERSION').read_text(encoding='utf-8-sig').strip()
if not version or any(c not in '0123456789.' for c in version):
    raise ValueError('Invalid release version')
files = ['CONTRIBUTING.md','SECURITY.md','CHANGELOG.md','VERSION','README.md','DEPLOYMENT.md','OPERATIONS.md','API.md','RESEARCH.md',
         'LICENSE','Dockerfile','Dockerfile.gpu','.dockerignore','.env.example','.gitignore',
         'compose.yaml','compose.gpu.yaml','compose.cpu-throughput.yaml','deploy.py','server.py','api_compat.py','healthcheck.py','start.sh','start.ps1',
         'requirements.txt','requirements-linux.lock','requirements-dev.txt','requirements-windows-gpu.txt','pytest.ini']
for folder in ['static','scripts','tests','skills','evidence','docs','.github']:
    for file in (root/folder).rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts:
            if file.is_symlink():
                raise ValueError(f'Symlink not allowed in release: {file}')
            files.append(str(file.relative_to(root)))
dist = root/'dist'; dist.mkdir(exist_ok=True)
archive = dist/f'caption-local-{version}.tar.gz'
with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as compressed:
    with tarfile.open(fileobj=compressed,mode='w') as tar:
        for name in sorted(set(files)):
            path=root/name
            info=tar.gettarinfo(str(path),arcname=f'caption-local-{version}/{name}')
            info.uid=info.gid=info.mtime=0; info.uname=info.gname=''
            info.mode=0o755 if name.endswith('.sh') else 0o644
            with path.open('rb') as data: tar.addfile(info,data)
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
(dist/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}\n' for item in sorted(dist.glob('caption-local-*.tar.gz'))), encoding='utf-8')
print(archive)
print(checksum)
