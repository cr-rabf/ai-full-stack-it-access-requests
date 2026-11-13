"""Install the stdlib-only application into a virtual environment, entirely offline."""
import argparse
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    prefix = args.prefix.resolve()
    destination = prefix / "lib/access-requests"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "access_requests", destination / "access_requests", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(source / "snapshot.schema.json", destination / "snapshot.schema.json")
    shutil.copyfile(source / "requirements.lock", destination / "requirements.lock")
    (destination / "materials").mkdir(exist_ok=True)
    shutil.copyfile(source / "materials/office-policy.md", destination / "materials/office-policy.md")
    binary = prefix / "bin/access-requests"
    binary.parent.mkdir(exist_ok=True)
    binary.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\nimport sys\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/access-requests'))\n"
        "from access_requests.cli import main\nraise SystemExit(main())\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    print(f"Installed {binary}")


if __name__ == "__main__":
    main()
