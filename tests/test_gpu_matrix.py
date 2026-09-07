"""A failed benchmark cell must fail the CLI while retaining every attempted cell."""
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


def test_matrix_retains_failed_cells_and_returns_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['gpu_matrix.py', '--models', 'small',
        '--precisions', 'float16', '--workers', '1', '--skip-cpu', '--output', str(tmp_path)])
    monkeypatch.setattr(subprocess, 'check_output', lambda *args, **kwargs: '')
    results = iter([1, 0])  # Quality failure must survive a later successful profile.
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs:
        subprocess.CompletedProcess(command, next(results)))
    script = Path(__file__).resolve().parents[1] / 'scripts/gpu_matrix.py'
    with pytest.raises(SystemExit, match='failed configurations'):
        runpy.run_path(str(script), run_name='__main__')
    status = json.loads((tmp_path / 'matrix-status.json').read_text(encoding='utf-8'))
    assert [cell['exit_code'] for cell in status] == [1, 0]
    assert all((tmp_path / (cell['name'] + '.log')).exists() for cell in status)
