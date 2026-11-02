"""Safe file operations: search, read, and write strictly within allowlisted folders."""

from __future__ import annotations

import os
from pathlib import Path

from orin.config.settings import OrinConfig, get_config
from orin.security.policy import is_path_allowlisted, sanitize_external_content


def search_files(
    query: str,
    config: OrinConfig | None = None,
    extension: str | None = None,
    limit: int = 20,
) -> list[str]:
    """Finds files matching keyword or extension within allowlisted folders."""
    cfg = config or get_config()
    allowlist = cfg.security.allowlisted_folders
    query_lower = query.lower().strip()
    ext_lower = f".{extension.lstrip('.').lower()}" if extension else None

    matches: list[str] = []
    for folder_str in allowlist:
        folder = Path(folder_str)
        if not folder.exists() or not folder.is_dir():
            continue

        try:
            for root, _, files in os.walk(folder):
                for f in files:
                    if ext_lower and not f.lower().endswith(ext_lower):
                        continue
                    if query_lower and query_lower not in f.lower():
                        continue

                    full_path = Path(root) / f
                    if is_path_allowlisted(full_path, allowlist):
                        matches.append(str(full_path))
                        if len(matches) >= limit:
                            return matches
        except Exception:
            continue

    return matches


def read_file_safe(
    path: str | Path,
    config: OrinConfig | None = None,
    max_bytes: int = 150_000,
) -> tuple[bool, str]:
    """Reads a file safely from an allowlisted folder with prompt-injection defense.

    Returns (success, content_or_error_message).
    """
    cfg = config or get_config()
    allowlist = cfg.security.allowlisted_folders

    if not is_path_allowlisted(path, allowlist):
        return (
            False,
            f"Security Error: Access denied to path '{path}'. Path is not in allowlisted folders.",
        )

    target = Path(path).resolve()
    if not target.exists() or not target.is_file():
        return False, f"File does not exist: '{path}'."

    try:
        size = target.stat().st_size
        if size > max_bytes:
            # Read first max_bytes
            with open(target, encoding="utf-8", errors="replace") as f:
                raw_text = f.read(max_bytes)
            raw_text += f"\n... [Truncated: File size ({size} bytes) exceeds limit ({max_bytes} bytes)]"
        else:
            raw_text = target.read_text(encoding="utf-8", errors="replace")

        # Sanitize against prompt injection
        safe_text = sanitize_external_content(raw_text)
        return True, safe_text

    except Exception as e:
        return False, f"Failed to read file '{path}': {e}"


def write_file_safe(
    path: str | Path,
    content: str,
    config: OrinConfig | None = None,
    append: bool = False,
) -> tuple[bool, str]:
    """Writes or appends to a file strictly within allowlisted folders.

    Returns (success, message).
    """
    cfg = config or get_config()
    allowlist = cfg.security.allowlisted_folders

    if not is_path_allowlisted(path, allowlist):
        return (
            False,
            f"Security Error: Write denied to path '{path}'. Path is not in allowlisted folders.",
        )

    try:
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)

        verb = "Appended to" if append else "Saved"
        return True, f"{verb} file successfully: {target.name}"
    except Exception as e:
        return False, f"Failed to write file '{path}': {e}"
