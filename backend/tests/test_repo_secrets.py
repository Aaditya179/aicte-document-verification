"""No secret is tracked by git: no env files, and nothing that looks like a Supabase or Groq key."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# A JWT (Supabase anon or service-role key), a Supabase secret key, or a Groq key
SECRET_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
]


def _tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / p for p in out.splitlines() if p]


def test_no_env_file_is_tracked():
    env_files = [p.name for p in _tracked_files() if re.fullmatch(r"\.env(\..+)?", p.name) and p.name != ".env.example"]
    assert env_files == []


def test_no_key_is_tracked():
    leaks = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(p.search(text) for p in SECRET_PATTERNS):
            leaks.append(str(path.relative_to(ROOT)))
    assert leaks == []
