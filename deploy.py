"""Portable bootstrap/launcher. Uses only Python's standard library."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['run', 'setup', 'download', 'doctor'], default='run')
    parser.add_argument('--venv', type=Path, default=ROOT / '.venv')
    parser.add_argument('--model', default='small')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--beam-size', type=int, choices=range(1,6), default=5)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--max-streams', type=int, default=12)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--log-requests', action='store_true')
    parser.add_argument('--device', choices=['cpu', 'cuda', 'auto'], default='cpu')
    parser.add_argument('--compute-type', choices=['auto', 'int8', 'float32', 'float16', 'int8_float16'], default='auto')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error('Install Python 3.12 or newer (3.12 is tested).')
    if args.threads < 1 or not 1 <= args.workers <= 8 or not 1 <= args.max_streams <= 64 or not 1 <= args.port <= 65535:
        parser.error('Threads must be positive; workers 1–8; streams 1–64; port 1–65535')
    env_dir = args.venv.expanduser().resolve()
    python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    def run(*command):
        subprocess.run([str(c) for c in command], cwd=ROOT, check=True)

    if args.command == 'setup' or (args.command == 'run' and not python.exists()):
        if args.offline:
            parser.error('Offline run requires an existing environment. Run setup and download online first.')
        print(f'Installing dependencies into {env_dir}', flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)
        requirements = 'requirements-linux.lock' if sys.platform == 'linux' else 'requirements.txt'
        run(python, '-m', 'pip', 'install', '-r', ROOT / requirements)
    if not python.exists():
        parser.error('Environment missing. Run: python deploy.py setup')
    if args.command == 'setup':
        print('Setup complete. Next: python deploy.py run', flush=True)
    elif args.command == 'doctor':
        run(python, '-m', 'pip', 'check')
        run(python, '-c', 'import server, ctranslate2; print("Runtime imports OK"); print("CUDA devices:", ctranslate2.get_cuda_device_count()); print("CPU types:", sorted(ctranslate2.get_supported_compute_types("cpu")))')
        print('Runtime ready. This check does not download models or test a microphone.', flush=True)
    elif args.command == 'download':
        run(python, '-c', 'from server import Engine; import sys; Engine(sys.argv[1], offline=sys.argv[2] == "1"); print("Model ready")', args.model, '1' if args.offline else '0')
    else:
        print(f'Open http://localhost:{args.port} once the server is ready. Ctrl+C stops it.', flush=True)
        command = [str(python), str(ROOT / 'server.py'), '--model', args.model,
                   '--port', str(args.port), '--threads', str(args.threads),
                   '--beam-size', str(args.beam_size), '--workers', str(args.workers), '--max-streams', str(args.max_streams),
                   '--device', args.device, '--compute-type', args.compute_type]
        if args.offline:
            command.append('--offline')
        if args.log_requests:
            command.append('--log-requests')
        if os.name != 'nt':
            os.execv(str(python), command)
        else:
            run(*command)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f'Command failed (exit {exc.returncode}). Fix the error above and rerun setup or doctor.', file=sys.stderr)
        sys.exit(exc.returncode)
    except KeyboardInterrupt:
        pass
