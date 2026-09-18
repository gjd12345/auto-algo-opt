"""Install a fresh optics wheel outside checkout and verify packaged entrypoints."""
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    package = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="optics-wheel-") as name:
        root = Path(name)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", str(package), "-w", str(root / "wheels")], check=True)
        subprocess.run([sys.executable, "-m", "venv", str(root / "env")], check=True)
        python = root / "env" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        wheel, = (root / "wheels").glob("*.whl")
        subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)], cwd=root, check=True)
        subprocess.run([str(python), "-I", "-c",
            "import artifact_session.runtime, optics_backend.offline; from artifact_session.contracts import hashes,skill_path; "
            "assert (skill_path()/'references/protocol.md').is_file(); assert hashes()['skill_hash']; "
            "print('outside_checkout_wheel: PASS')"], cwd=root, check=True)
        for module in ("artifact_session", "optics_backend"):
            subprocess.run([str(python), "-I", "-m", module, "--help"], cwd=root, check=True)


if __name__ == "__main__":
    main()
