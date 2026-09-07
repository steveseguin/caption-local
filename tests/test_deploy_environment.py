"""A shared checkout must not overwrite the other operating system's environment."""
import os
from pathlib import Path
import subprocess
import sys


def test_setup_preserves_other_platform_environment(tmp_path):
    other = tmp_path / ('bin/python' if os.name == 'nt' else 'Scripts/python.exe')
    other.parent.mkdir(parents=True)
    other.write_bytes(b'existing interpreter must not change')
    config = tmp_path / 'pyvenv.cfg'
    config.write_bytes(b'existing environment configuration')
    before = {path.relative_to(tmp_path):path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'deploy.py'),
        'setup', '--venv', str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'another platform' in result.stderr and '--venv' in result.stderr
    after = {path.relative_to(tmp_path):path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    assert after == before
