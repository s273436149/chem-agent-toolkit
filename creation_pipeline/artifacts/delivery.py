"""Direct-file validation, durable delivery receipts and reliable chunk writes."""
from pathlib import Path
import base64
from creation_pipeline.records import read_json, write_json, safe_relative, digest, sanitized, has_link
from creation_pipeline.artifacts.package import manifest, ROLES
from creation_pipeline.models import exceeded


def inside(run, path):
    root, target = Path(run).resolve(), Path(path).absolute()
    if has_link(target) or not target.resolve().is_relative_to(root):
        raise ValueError("Helper target must be an unlinked path inside this run")
    return target


def validate_package(package, limit=None):
    package = Path(package)
    files = manifest(package)
    if not any(f["path"] == "SKILL.md" for f in files):
        raise ValueError("Missing SKILL.md")
    if exceeded(sum(f["bytes"] for f in files), limit):
        raise ValueError("Package exceeds explicit package_bytes limit")
    for f in files:
        parts = Path(f["path"]).parts
        if f["path"] != "SKILL.md" and (len(parts) < 2 or parts[0] not in ROLES):
            raise ValueError("Unsupported file role: " + f["path"])
        from creation_pipeline.resources.intake import exclusion
        if exclusion(Path(f["path"])):
            raise ValueError("Excluded runtime file: " + f["path"])
        if f["path"] == "SKILL.md" and not f["bytes"]:
            raise ValueError("Empty SKILL.md")
        if Path(f["path"]).suffix.lower() in {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".sh"}:
            import re
            carry = ""
            with (package / f["path"]).open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    text = carry + chunk.decode("utf-8", errors="ignore")
                    if re.search(r"\b(?:sk-[\w-]{12,}|nvapi-[\w-]{12,})", text):
                        raise ValueError("Possible credential literal in " + f["path"])
                    import os
                    if any(len(v) >= 8 and re.search(r"(?i)(token|secret|password|api_?key)", k) and v in text for k, v in os.environ.items()):
                        raise ValueError("Environment credential literal in " + f["path"])
                    carry = text[-256:]
    return files


def finish(run, package, token, metadata=None):
    phase_path = Path(run) / "active-phase.json"
    if phase_path.exists() and read_json(phase_path)["phase"] != "author":
        raise ValueError("Only the author stage may finalize runtime packages")
    package = inside(run, package)
    state = read_json(Path(run) / "resource-state.json")
    data = read_json(inside(run, metadata)) if metadata else {}
    for key in ("tests", "issues", "notes"):
        data.setdefault(key, [])
        if not isinstance(data[key], list):
            raise ValueError(key + " must be an array")
    for test in data["tests"]:
        from creation_pipeline.validation.runtime import validate_test
        validate_test(test)
        if not test.get("evidence") or not test.get("purpose"):
            raise ValueError("Checks need source evidence and purpose")
    for issue in data["issues"]:
        if not isinstance(issue, dict) or type(issue.get("blocking")) is not bool or not issue.get("description"):
            raise ValueError("Issues need description and blocking boolean")
    entry = data.get("entry")
    if entry is not None:
        # The declaration selects the entry; it is validated against the delivered
        # package during runtime preparation, never trusted on its own here.
        import re
        if not isinstance(entry, dict) or set(entry) - {"kind", "path", "block_index", "code_sha256"}:
            raise ValueError("Entry declaration supports only kind, path, block_index and code_sha256")
        if entry.get("kind") not in ("script", "markdown_python"):
            raise ValueError("Entry declaration kind must be script or markdown_python")
        if not isinstance(entry.get("path"), str) or not entry["path"].strip():
            raise ValueError("Entry declaration needs a nonempty path")
        if "block_index" in entry and (type(entry["block_index"]) is not int or entry["block_index"] < 0):
            raise ValueError("Entry block_index must be a nonnegative integer")
        if "code_sha256" in entry and not re.fullmatch(r"[0-9a-f]{64}", str(entry["code_sha256"])):
            raise ValueError("Entry code_sha256 must be a lowercase SHA-256 hex digest")
    data.update(completed=True, token=token, package=str(package),
                files=validate_package(package, state["config"]["limits"]["package_bytes"]))
    path = safe_relative(Path(run), "deliveries/" + package.name + ".json")
    write_json(path, sanitized(data))
    return {"status": "saved", "delivery": str(path), "files": len(data["files"])}


def delivered(run, package, token):
    path = safe_relative(Path(run), "deliveries/" + Path(package).name + ".json")
    if not path.exists():
        return None
    data = read_json(path)
    if data.get("completed") and data.get("token") == token and data.get("files") == manifest(package):
        return data
    return None


def write_chunk(package, relative, encoded, append=False):
    root = Path(package).absolute()
    registered = next((p for p in (root, *root.parents) if (p / "resource-state.json").is_file()), None)
    if registered is None:
        raise ValueError("Chunk writer requires a registered run workspace")
    inside(registered, root)
    phase = read_json(registered / "active-phase.json").get("phase") if (registered / "active-phase.json").exists() else None
    if phase in ("discovery", "review") and root.is_relative_to(registered / "bundle"):
        raise ValueError("This stage must not write official skill files")
    # Package path comes from the supplied run context; symlink escapes are refused.
    target = safe_relative(root, relative)
    raw = base64.b64decode(encoded, validate=True)
    raw.decode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with target.open("ab") as stream:
            stream.write(raw)
    else:
        temporary = target.with_name(target.name + ".writing")
        temporary.write_bytes(raw)
        temporary.replace(target)
    return {"path": str(target), "bytes": target.stat().st_size}
