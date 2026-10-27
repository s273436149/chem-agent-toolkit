"""Attach one grounded runtime plan to the native candidate, never author a skill."""
import copy
import json
import re
import shutil
import time
from pathlib import Path

from creation_pipeline.artifacts.evidence import checked_copy
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint, versioned
from creation_pipeline.records import safe_relative, write_json, redact, sanitized
from . import planner


class RuntimeBlocked(ValueError):
    def __init__(self, code, detail, lane="environment"):
        self.code, self.lane = code, lane
        super().__init__(detail)


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) - {'binding', 'plan', 'options', 'resource_refs', 'constraints', 'locked_cases', 'previous_plan', 'feedback'}:
        raise ValueError('Unsupported runtime preparation settings')
    for key in ('binding', 'plan', 'options', 'resource_refs'):
        if key in spec and not isinstance(spec[key], dict):
            raise ValueError('runtime.' + key + ' must be an object')
    if not isinstance(spec.get('constraints', []), list) or any(not isinstance(s, str) for s in spec.get('constraints', [])):
        raise ValueError('Runtime constraints must be text items')
    for ref in spec.get('resource_refs', {}).values():
        if not isinstance(ref, dict) or set(ref) - {'path', 'sha256', 'env'} or any(not isinstance(v, str) for v in ref.values()):
            raise ValueError('Resource references support only path/sha256 or environment-variable names; no credential values')
    for entry in spec.get('plan', {}).get('environment', []):
        if isinstance(entry, dict) and re.search(r'(?i)password|credential|secret|token|api_?key', str(entry.get('name', ''))):
            raise ValueError('Credential values cannot be supplied as Docker environment literals')
    if redact(json.dumps(spec, ensure_ascii=False)) != json.dumps(spec, ensure_ascii=False):
        raise ValueError('Runtime settings contain credential-like literals; use references')
    planner.options(spec.get('options', {}))


def bind(package, sources, proposal=None, entry=None):
    """Automatic binding requires byte identity; adapted entrypoints need explicit evidence.

    ``entry`` restricts the automatic byte-identity search to one declared delivered
    path, so a declaration cannot be satisfied by a different file that happens to
    equal a source.
    """
    files = manifest(package)
    source_files = [(s, f) for s in sources for f in s["inventory"]]
    if proposal is None:
        matches = [(f, s, sf) for f in files if f["path"].endswith((".py", ".sh"))
                   and (entry is None or f["path"] == entry)
                   for s, sf in source_files if f["sha256"] == sf["sha256"]]
        if len(matches) != 1:
            raise RuntimeBlocked("binding_unresolved", "No unique delivered executable/source identity; configure a binding", "binding")
        f, s, sf = matches[0]
        proposal = {"entry": f["path"], "source_id": s["id"], "source_path": sf["path"], "association": "identical"}
    p = copy.deepcopy(proposal)
    try:
        entry = next(f for f in files if f["path"] == p["entry"])
        source, original = next((s, f) for s, f in source_files if s["id"] == p["source_id"] and f["path"] == p["source_path"])
        safe_relative(package, p["entry"])
        if p.get("association") == "identical":
            if entry["sha256"] != original["sha256"]:
                raise ValueError("Claimed identical entry differs from source")
        elif p.get("association") == "explicit":
            # Explicit user association is not a model's self-certification.
            if not p.get("reason") or not p.get("quote"):
                raise ValueError("Explicit association needs reason and exact source quote")
            root = Path(source["path"])
            text = (root if root.is_file() else safe_relative(root, original["path"])).read_text(encoding="utf-8")
            if p["quote"] not in text:
                raise ValueError("Binding source quote mismatch")
        else:
            raise ValueError("Unsupported association")
        p.update(entry_sha256=entry["sha256"], source_sha256=original["sha256"])
        return p
    except (KeyError, StopIteration, OSError, ValueError) as exc:
        raise RuntimeBlocked("binding_unresolved", str(exc), "binding") from exc


def handoff(package, sources, destination):
    """One verified source handoff shared by planner and context renderer."""
    destination.mkdir(parents=True)
    for f in manifest(package):
        checked_copy(safe_relative(package, f["path"]), safe_relative(destination, "package/" + f["path"]), f["sha256"])
    for source in sources:
        root = Path(source["path"])
        for f in source["inventory"]:
            checked_copy(root if root.is_file() else safe_relative(root, f["path"]),
                         safe_relative(destination, "sources/" + source["id"] + "/" + f["path"]), f["sha256"])


def validate(p, index, source, binding, opts, locked=None):
    if redact(json.dumps(p, ensure_ascii=False)) != json.dumps(p, ensure_ascii=False):
        raise RuntimeBlocked("unsafe_plan", "Plan contains credential-like literals", "environment")
    cases, _, total = planner.validate_plan(p, index, source, [c for c in locked if c.get('origin') != 'authored_check'] if locked else None)
    from .entry import runtime_path
    entry = runtime_path(binding)
    if p["script"] != entry or "/opt/skill/" + entry not in p["entrypoint"]:
        raise RuntimeBlocked("entry_mismatch", "Plan must invoke the actual delivered entry", "binding")
    if any(c.get("timeout_seconds", 30) > opts["test_seconds"] for c in cases):
        raise planner.PlanningError("Case exceeds explicit operation timeout")
    if opts["max_context_bytes"] is not None and total > opts["max_context_bytes"]:
        raise planner.BudgetExceeded("Explicit context byte limit reached")
    return cases


def propose(source, binding, audit, opts, constraints=None, locked=None, feedback=None, call_guard=None, previous=None):
    """Reuse planner reads/patches; stop repeated diagnoses instead of hidden quotas."""
    import itertools
    deadline = None if opts["total_seconds"] is None else time.monotonic() + opts["total_seconds"]
    attempts = itertools.count() if opts["max_attempts"] is None else range(opts["max_attempts"])
    diagnoses = set()
    from .entry import runtime_path
    for number in attempts:
        p, index, _ = planner.plan(source, {"script": runtime_path(binding),
            "constraints": ["Invoke the unchanged delivered package entry, not only the upstream tool."] + (constraints or [])},
            Path(audit) / str(number), opts, deadline, feedback=feedback, previous=previous, call_guard=call_guard)
        try:
            cases = validate(p, index, source, binding, opts, locked)
            return p, index, cases
        except (planner.PlanningError, ValueError) as exc:
            diagnostic = str(exc)
            if diagnostic in diagnoses:
                raise RuntimeBlocked("planning_no_progress", diagnostic) from exc
            diagnoses.add(diagnostic)
            feedback = {"rejected_plan": p, "read_files": index.get("read_files", []),
                        "source_fingerprint": fingerprint(index["files"]), "diagnostic": diagnostic}
            write_json(Path(audit) / str(number) / "rejection.json", sanitized(feedback))
    raise RuntimeBlocked("explicit_attempt_limit", "Configured planning attempt limit reached")


def render(source, target, plan, cases):
    """Container-only installation; final delivered code copied unchanged."""
    target.mkdir(parents=True)
    names = set(plan["source_files"]) | {"package/" + f["path"] for f in manifest(source / "package")}
    for name in sorted(names):
        p = safe_relative(source, name)
        from creation_pipeline.records import file_digest
        checked_copy(p, safe_relative(target, name), file_digest(p))
    for f in plan["generated_files"]:
        p = safe_relative(target, f["path"])
        if p.exists() or f["path"].startswith(("package/", "sources/")):
            raise planner.PlanningError("Generated installation file may not replace delivery/source")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["content"], encoding="utf-8")
    lines = ["FROM " + plan["base_image"], "WORKDIR /opt/skill", "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp"]
    lines += ["ENV " + e["name"] + "=" + json.dumps(e["value"]) for e in plan["environment"]]
    prefix = plan["build_layout"]["prefix_steps"]
    if prefix:
        lines += ["COPY " + json.dumps([n, "./" + n]) for n in plan["build_layout"]["dependency_files"]]
        lines += ["RUN " + s["command"] for s in plan["steps"][:prefix]]
    lines += ["COPY . ./"] + ["RUN " + s["command"] for s in plan["steps"][prefix:]]
    lines += ["USER 10001:10001", "ENTRYPOINT " + json.dumps(plan["entrypoint"])]
    (target / "Dockerfile").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (target / ".dockerignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")


def rebind(record, binding, environment, acceptance):
    d = record["delivery"]
    old_revision = d["revision_id"]
    for key, value in (("bindings", binding), ("environment", environment), ("acceptance", acceptance)):
        old = d["inputs"][key]
        d["inputs"][key] = versioned(value, old["version"] + (old["sha256"] != fingerprint(value)))
    d["revision_id"] = "rev-" + fingerprint(d["inputs"])
    d["fingerprints"] = {k: fingerprint(d["inputs"][k]) for k in d["fingerprints"]}
    if old_revision != d["revision_id"]:
        d["parent_revision"] = old_revision
    d["execution"] = {"status": "not_run", "attempts": [], "reason": "This revision requires fresh bound execution evidence"}
    d["qualification"] = {"accepted": False, "reason": "Docker build is not business acceptance"}


def prepare(record, package, sources, workspace, spec, executor, call_guard=None, review_evidence=None):
    """Return immutable materials plus a diagnostic; deterministic blockers do not call models."""
    validate_spec(spec)
    d = record["delivery"]
    if d["mode"] == "draft" or d["inputs"]["requirement"]["status"] == "not_required" or d["content"]["status"] != "passed":
        return None
    target = Path(workspace) / "materials"
    target.mkdir(parents=True)
    result = {"status": "runtime_blocked", "gaps": [], "model_calls": 0}
    def counted_call_guard():
        if call_guard is not None:
            call_guard()
        # Count admitted invocation attempts, including failed transports, not
        # only successful planner receipts. Entry association uses models too.
        result['model_calls'] += 1
    binding = None
    opts = planner.options(spec.get("options", {}))
    if opts["total_seconds"] is not None:
        deadline = time.monotonic() + opts["total_seconds"]
        executor.deadline = min(executor.deadline, deadline) if executor.deadline is not None else deadline
    try:
        if d["inputs"]["requirement"]["status"] == "unknown":
            raise RuntimeBlocked("requirements_unknown", d["inputs"]["requirement"]["reason"], "requirement")
        from .entry import associate, materialize, preflight
        host = None
        declared = record.get('entry_declaration')
        if spec.get('binding') is not None:
            # 1. The caller bound the entry explicitly. It is validated and a failure
            # blocks; the entry is never silently re-derived.
            binding = bind(package, sources, spec['binding'])
            binding['declaration_source'] = 'user_binding'
        elif declared is not None:
            # 2. The author declared the entry. The declaration selects, then the
            # ordinary checks decide whether it is trustworthy.
            entry = preflight(package, declared)
            binding = None
            if entry['kind'] == 'script':
                try:
                    binding = bind(package, sources, entry=entry['entry'])
                except RuntimeBlocked:
                    binding = None
            if binding is None:
                host = executor.host()
                if host['gaps']:
                    result['gaps'].extend(host['gaps'])
                    raise RuntimeBlocked('planning_deferred', 'Docker unavailable; entry association and planning deferred without model calls')
                binding = associate(record, package, sources, target / 'association', opts,
                                    counted_call_guard, executor.deadline, entry=entry)
            binding['declaration'] = entry.get('declaration')
            binding['declaration_source'] = 'author_declaration'
        else:
            # 3. No declaration: conservative recognition of a single candidate.
            try:
                binding = bind(package, sources)
                binding['declaration_source'] = 'identical_bytes'
            except RuntimeBlocked:
                preflight(package)
                host = executor.host()
                if host['gaps']:
                    result['gaps'].extend(host['gaps'])
                    raise RuntimeBlocked('planning_deferred', 'Docker unavailable; association and planning deferred without model calls')
                binding = associate(record, package, sources, target / 'association', opts, counted_call_guard, executor.deadline)
                binding['declaration_source'] = 'conservative'
        write_json(target / "binding.json", binding)
        source = Path(workspace) / "handoff"
        handoff(package, sources, source)
        materialize(package, binding, source)
        from .entry import source_view
        write_json(source / 'source-identities.json', source_view(sources))
        index = planner.inventory(source, opts)
        host = host if host is not None else executor.host()
        p = copy.deepcopy(spec.get("plan"))
        if p is None:
            if host["gaps"]:
                result["gaps"].extend(host["gaps"])
                raise RuntimeBlocked("planning_deferred", "Docker unavailable; no model called. Supply a plan to prepare offline")
            planning_opts = dict(opts)
            if executor.deadline is not None and executor.deadline != float("inf"):
                remaining = executor.deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeBlocked("explicit_budget", "Explicit runtime time limit reached")
                planning_opts["total_seconds"] = max(1, int(remaining))
            entry_constraints = list(spec.get('constraints', []))
            if binding.get('kind') == 'markdown_python':
                entry_constraints += ['entry/skill.py is the exact unchanged Python block extracted from package/SKILL.md; '
                    'do not generate or alter business code. Invocation contract: ' + binding['invocation'],
                    'Existing author checks are additionally locked and executed against the actual Markdown. ' +
                    json.dumps(d['inputs']['acceptance']['payload'], ensure_ascii=False)]
            p, index, _ = propose(source, binding, target / "planning", planning_opts, entry_constraints, spec.get("locked_cases"),
                                  feedback=spec.get('feedback'), call_guard=counted_call_guard, previous=spec.get('previous_plan'))
        else:
            index["read_files"] = list(index["files"])
        if redact(json.dumps(p, ensure_ascii=False)) != json.dumps(p, ensure_ascii=False):
            raise RuntimeBlocked("unsafe_plan", "Plan contains credential-like literals")
        cases = validate(p, index, source, binding, opts, spec.get("locked_cases"))
        from .checks import mapped_checks
        original_acceptance = d['inputs']['acceptance']['payload'] or {}
        cases += mapped_checks(original_acceptance, p, [s['id'] for s in sources])
        if spec.get('locked_cases') is not None:
            by_name = {c['name']: c for c in cases}
            if any(fingerprint(by_name.get(c['name'])) != fingerprint(c) for c in spec['locked_cases']):
                raise planner.PlanningError('Environment repair changed locked tests or mapped checks')
        write_json(target / "proposed-plan.json", p)
        write_json(target / "locked-tests.json", {"cases": cases, "policy": json.loads(p["acceptance_json"])})
        render(source, target / "context", p, cases)
        write_json(target / "plan.json", p)
        if review_evidence is not None:
            write_json(target / 'independent-contract-review.json', review_evidence)
        (target / "README.md").write_text("Docker build materials only. No business acceptance has run.\n"
            "Build context: context/. Entrypoint is the unchanged delivered package.\n"
            "Run with runtime-validate using locked-tests.json; never substitute host execution.\n", encoding="utf-8")
        result["status"] = "prepared"
        old_acceptance = d["inputs"]["acceptance"]["payload"]
        author_tests = old_acceptance.get("author_tests", old_acceptance) if isinstance(old_acceptance, dict) else old_acceptance
        required_names = {r["description"] for r in p["resources"] if r["required_for_execution"]}
        resource_inputs = {key: {k: v for k, v in value.items() if k in {"sha256", "env"}}
                           for key, value in spec.get("resource_refs", {}).items() if key in required_names}
        rebind(record, binding, {"plan": p, "materials": manifest(target), "limits": opts, "resource_inputs": resource_inputs},
               {"cases": cases, "policy": json.loads(p["acceptance_json"]), "author_tests": author_tests})
    except (RuntimeBlocked, planner.PlanningError, planner.ModelUnavailable, OSError, ValueError, ImportError) as exc:
        result["gaps"].append({"code": getattr(exc, "code", "plan_unresolved"), "detail": redact(str(exc)),
                               "repair_lane": getattr(exc, "lane", "environment"),
                               "blocker_kind": getattr(exc, 'kind', 'unresolved_input')})
        rebind(record, binding, {"materials": manifest(target), "limits": opts, "incomplete": True}, d["inputs"]["acceptance"]["payload"])
        if getattr(exc, 'lane', None) == 'content' and getattr(exc, 'kind', None) == 'content_defect':
            d['content']['status'] = 'failed'
            record['content_status'] = 'failed'
        d["execution"] = {"status": "runtime_blocked", "attempts": [], "reason": result["gaps"][0]["detail"]}
        record["status"] = "blocked"
    record["runtime_preparation"] = result
    return target
