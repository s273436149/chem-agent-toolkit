"""Source association and deterministic delivered-entry materialization.

No business implementation is generated here. A Markdown entry is exactly one
unindented fenced Python block; its bytes, locator and delivery manifest are bound.
"""
import ast
import builtins
import hashlib
import json
import math
import re
import symtable
import time
from pathlib import Path

from creation_pipeline.records import safe_relative, write_json, file_digest, redact
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint


class EntryError(ValueError):
    def __init__(self, code, message, lane='binding', kind='unsupported_contract'):
        self.code, self.lane, self.kind = code, lane, kind
        super().__init__(message)


def markdown_entry(package):
    path = safe_relative(Path(package), 'SKILL.md')
    if not path.is_file():
        raise EntryError('entry_missing', 'Missing delivered SKILL.md', 'content', 'content_defect')
    raw = path.read_bytes()
    # Deliberately narrow: no nested/list-indented fences, concatenation or REPL.
    blocks = list(re.finditer(rb'^```(?:python|py)[ \t]*\r?\n(.*?)^```[ \t]*(?:\r?\n|$)', raw, re.M | re.S))
    openings = re.findall(rb'^[ \t]*[`~]{3,}(?:python|py)\b[^\r\n]*', raw, re.M)
    if len(blocks) != 1 or len(openings) != 1:
        raise EntryError('entry_unsupported', 'Require exactly one complete, unindented ```python block in SKILL.md; multiple/interactive/ambiguous blocks are unsupported')
    # A Python-looking fence inside a larger literal fence is documentation,
    # not an executable block. Track outer backtick/tilde fences before binding.
    active = None
    top_level = []
    offset = 0
    for line in raw.splitlines(keepends=True):
        fence = re.match(rb'^ {0,3}(`{3,}|~{3,})([^\r\n]*)', line)
        if fence:
            marker, tail = fence.groups()
            if active is None:
                active = marker
                top_level.append(offset)
            elif marker[:1] == active[:1] and len(marker) >= len(active) and not tail.strip():
                active = None
        offset += len(line)
    if blocks[0].start() not in top_level:
        raise EntryError('entry_unsupported', 'Python fence is inside a literal Markdown code block')
    block = blocks[0]; code = block.group(1)
    try:
        text = code.decode('utf-8')
        tree = ast.parse(text)
        if not tree.body:
            raise SyntaxError('empty Python block')
    except (UnicodeError, SyntaxError) as exc:
        raise EntryError('entry_invalid', 'Delivered Python block is incomplete: ' + str(exc), 'content', 'content_defect') from exc
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {'input', 'breakpoint', 'exec', 'eval'} for n in ast.walk(tree)):
        raise EntryError('entry_unsupported', 'Interactive/dynamically constructed Python entry is unsupported')
    table = symtable.symtable(text, str(path), 'exec')
    defined = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    allowed = defined | set(dir(builtins)) | {'__name__', '__file__', '__package__', '__doc__'}
    def unresolved(scope):
        names = {s.get_name() for s in scope.get_symbols() if s.is_referenced() and s.is_global() and s.get_name() not in allowed}
        for child in scope.get_children():
            names |= unresolved(child)
        return names
    missing = unresolved(table)
    if missing:
        raise EntryError('entry_context_missing', 'Python entry needs undeclared context: ' + ', '.join(sorted(missing)), 'content', 'content_defect')
    return {'kind': 'markdown_python', 'entry': 'SKILL.md', 'runtime_entry': 'entry/skill.py',
            'extraction': {'rule': 'single-unindented-python-fence-v1', 'block_index': 0,
                'start_byte': block.start(1), 'end_byte': block.end(1),
                'start_line': raw[:block.start(1)].count(b'\n') + 1,
                'markdown_sha256': hashlib.sha256(raw).hexdigest(),
                'code_sha256': hashlib.sha256(code).hexdigest()}}, code


def preflight(package):
    """Derive an entry only when the package has exactly one candidate.

    Selection is explicit: a unique markdown python block, or exactly one
    delivered script when no usable markdown block exists. Two possible entries
    is ambiguity, and ambiguity is refused rather than resolved by preference.
    """
    scripts = [f['path'] for f in manifest(package) if f['path'].endswith(('.py', '.sh'))]
    markdown, markdown_error = None, None
    try:
        markdown = markdown_entry(package)[0]
    except EntryError as exc:
        markdown_error = exc
    if scripts:
        if len(scripts) > 1:
            raise EntryError('entry_ambiguous',
                             'Multiple delivered scripts need an explicit entry selection; got ' + ', '.join(sorted(scripts)),
                             kind='unresolved_input')
        if markdown is not None:
            raise EntryError('entry_ambiguous',
                             'Both a markdown python block and a delivered script could be the entry (' +
                             ', '.join(sorted(scripts)) + '); select one explicitly', kind='unresolved_input')
        binding = {'kind': 'script', 'entry': scripts[0], 'runtime_entry': 'package/' + scripts[0]}
        if markdown_error is not None:
            binding['markdown_candidate_rejected'] = {'code': markdown_error.code,
                                                      'detail': str(markdown_error)[:300]}
        return binding
    if markdown is not None:
        return markdown
    if markdown_error is not None:
        # Preserve the original lane/kind: a missing or unsupported markdown
        # entry is a delivery-contract problem, not an unresolved input choice.
        raise markdown_error
    raise EntryError('entry_missing', 'No delivered script and no markdown python block to bind',
                     'content', 'content_defect')


def runtime_path(binding):
    return binding.get('runtime_entry', 'package/' + binding['entry'])


def source_view(sources):
    """Presentation-only provenance, including honest handling of legacy records."""
    return [{'id': s['id'], 'inventory': s['inventory'], 'snapshot_fingerprint': fingerprint(s['inventory']),
             'upstream': s.get('upstream'), 'carrier_repository': s.get('carrier_repository'),
             'legacy_reference': {'value': s.get('resolved_ref'), 'meaning': 'Not verified as an upstream version unless accompanied by upstream/repo provenance'},
             'repo': s.get('repo'), 'url': s.get('url')} for s in sources]


def materialize(package, binding, target):
    if binding.get('kind') != 'markdown_python':
        return
    actual, code = markdown_entry(package)
    if any(binding.get(k) != actual[k] for k in ('entry', 'runtime_entry', 'extraction')):
        raise ValueError('Markdown entry locator or bytes differ from bound delivery')
    output = safe_relative(Path(target), runtime_path(binding))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(code)


def verify_material(package, binding, material):
    if binding.get('kind') != 'markdown_python':
        return
    actual, code = markdown_entry(package)
    if any(binding.get(k) != actual[k] for k in ('entry', 'runtime_entry', 'extraction')):
        raise ValueError('Markdown entry changed after binding')
    if safe_relative(Path(material), runtime_path(binding)).read_bytes() != code:
        raise ValueError('Extracted entry differs from exact delivered code bytes')


def associate(record, package, sources, audit, opts, guard=None, deadline=None):
    """One bounded proposal and independent semantic review, never self-approval."""
    from . import model_call
    from .review import review_snapshot
    def limits():
        if deadline is None or not math.isfinite(deadline):
            return opts['model_timeout'], opts['total_seconds']
        remaining = deadline - time.monotonic()
        if remaining < 1:
            raise EntryError('explicit_budget', 'Explicit runtime time limit reached before association/review', 'environment', 'caller_limit')
        return min(opts['model_timeout'], int(remaining)), int(remaining)
    entry = preflight(package)  # deterministic failures never call a model
    audit = Path(audit); audit.mkdir(parents=True, exist_ok=True)
    source_text = []
    for s in sources:
        for f in s['inventory']:
            p = Path(s['path']) if Path(s['path']).is_file() else safe_relative(Path(s['path']), f['path'])
            if file_digest(p) != f['sha256']:
                raise ValueError('Binding source changed')
            try:
                text = p.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            source_text.append({'source_id': s['id'], 'path': f['path'], 'sha256': f['sha256'], 'text': text})
    fields = {'source_id': {'type': 'string'}, 'source_path': {'type': 'string'},
              'quote': {'type': 'string'}, 'reason': {'type': 'string'},
              'invocation': {'type': 'string'}, 'supported': {'type': 'boolean'}}
    schema = {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}
    prompt = ('Associate the actual delivered entry with an inspected upstream API/tool. Return supported=false if uncertain. '
              'Supply one contiguous verbatim substring from the chosen source file as quote proving the API relationship. '
              'Never concatenate separate excerpts, insert ellipses, or change whitespace in quote; put additional API explanations in reason. '
              'Explain both source and delivery scope, '
              'and describe interpreter, arguments/function inputs, working directory, outputs and necessary supports. '
              'Do not edit code or propose tests/expected outputs. A local carrier commit is NOT an upstream version.\n' +
              json.dumps({'entry': entry, 'delivery': [{'path': f['path'], 'text': safe_relative(Path(package), f['path']).read_text(encoding='utf-8', errors='replace')} for f in manifest(package)],
                          'source_identities': source_view(sources), 'sources': source_text}, ensure_ascii=False))
    if redact(prompt) != prompt:
        raise EntryError('unsafe_binding_source', 'Credential-like source material cannot enter association prompts', kind='unresolved_input')
    (audit / 'proposal-prompt.txt').write_text(prompt, encoding='utf-8')
    timeout, _ = limits()
    if guard:
        guard()
    proposal, receipt = model_call.call(prompt, schema, opts['model'], timeout=timeout, audit_dir=audit / 'model',
                                        transport=opts.get('transport', 'default'),
                                        progress_watch=opts.get('progress_watch', 'terminate'),
                                        reasoning=opts.get('reasoning_effort'),
                                        tier=opts.get('service_tier'))
    import jsonschema
    try:
        jsonschema.validate(proposal, schema)
    except jsonschema.ValidationError as exc:
        raise EntryError('binding_proposal_invalid', 'Association proposal schema: ' + exc.message, kind='unresolved_input') from exc
    if redact(json.dumps(proposal)) != json.dumps(proposal):
        raise EntryError('binding_proposal_invalid', 'Association proposal contains credential-like values', kind='unresolved_input')
    write_json(audit / 'proposal.json', proposal); write_json(audit / 'receipt.json', receipt)
    if not proposal['supported']:
        raise EntryError('binding_unresolved', proposal['reason'], kind='unresolved_input')
    candidates = [s for s in source_text if s['source_id'] == proposal['source_id'] and s['path'] == proposal['source_path']]
    if len(candidates) != 1 or not proposal['quote'].strip() or proposal['quote'] not in candidates[0]['text'] or not proposal['reason'] or not proposal['invocation']:
        raise EntryError('binding_unresolved', 'Association lacks a verified exact source citation and invocation', kind='unresolved_input')
    binding = dict(entry, association='reviewed', source_id=proposal['source_id'], source_path=proposal['source_path'],
                   source_sha256=candidates[0]['sha256'], quote=proposal['quote'], reason=proposal['reason'], invocation=proposal['invocation'],
                   entry_sha256=file_digest(safe_relative(Path(package), entry['entry'])), files=manifest(package))
    timeout, remaining = limits()
    reviewed = review_snapshot(record, package, sources, audit / 'review', proposed_binding=binding,
        model=opts['model'], timeout=timeout, total_seconds=remaining, call_guard=guard,
        transport=opts.get('transport', 'default'), reasoning_effort=opts.get('reasoning_effort'),
        service_tier=opts.get('service_tier'))
    write_json(audit / 'independent-review.json', reviewed)
    result = reviewed['review']
    if result['status'] != 'pass' or result.get('binding_verified') is not True or result.get('requirement_assessment') != 'confirmed':
        if result.get('resolution') == 'revise_files' and any(
                isinstance(f, dict) and f.get('blocking') and f.get('category') == 'file' for f in result.get('findings', [])):
            raise EntryError('entry_content_review_failed', json.dumps(result['findings'], ensure_ascii=False), 'content', 'content_defect')
        raise EntryError('binding_review_required', 'Independent review did not approve the source association and actual invocation', kind='unresolved_input')
    binding['review_sha256'] = fingerprint(reviewed)
    return binding
