"""Source-grounded acceptance contracts, checked before any execution.

Runtime evaluation lives in the portable runner; this module only checks evidence.
"""
import json
import re
from pathlib import Path


class ContractConflict(ValueError):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        self.lane = 'contract'
        self.code = 'contract_conflict'
        super().__init__('Inconsistent acceptance contract: ' + json.dumps(conflicts, ensure_ascii=False))


def consistency(cases):
    """Prove contradictions only within one invocation and one output channel.

    The runner's text is stdout, or output_file (unless capture_stdout). Never
    compare a file predicate to stdout merely because they belong to one case.
    This checks satisfiability, not whether either expectation is source-correct.
    """
    from .runner import subset
    conflicts = []
    for case in cases:
        if case.get('relation'):
            continue
        assertion = case.get('acceptance', {}).get('assertion', {})
        same_channel = not case.get('output_file') or case.get('capture_stdout')
        if 'stdout_equals' not in case or not same_channel:
            continue
        text = case['stdout_equals']
        kind = assertion.get('kind')
        reason = None
        try:
            if kind in {'json', 'jsonl'}:
                value = (json.loads(text.splitlines()[assertion['record_index']])
                         if kind == 'jsonl' else json.loads(text))
                for key in assertion['path']:
                    value = value[key]
                if not any(subset(expected, value) for expected in assertion['allowed_values']):
                    reason = 'Exact stdout field cannot satisfy typed allowed_values (no coercion or tolerance)'
            elif kind == 'stdout_equals' and text.strip() != assertion['value']:
                reason = 'Two exact assertions on stdout disagree'
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            reason = 'Exact stdout cannot satisfy the required JSON/JSONL path: ' + type(exc).__name__
        if reason:
            conflicts.append({'case': case['name'], 'channel': 'stdout', 'field': assertion.get('path'),
                              'assertions': ['stdout_equals', 'acceptance.assertion'], 'basis': reason})
    return conflicts


def grounded(record, index, source):
    if not isinstance(record, dict):
        return False
    path, quote = record.get('source_path'), record.get('source_quote')
    if path not in index.get('read_files', index['files']) or not isinstance(quote, str) or not quote.strip():
        return False
    target = (Path(source) / path).resolve()
    if not target.exists() and (path.startswith('entry/') or path == 'source-identities.json'):
        # Frozen deterministic materials live outside the delivery/source trees.
        target = (Path(source) / 'runtime/context' / path).resolve()
    return target.is_relative_to(Path(source).resolve()) and quote in target.read_text(encoding='utf-8')


def contracts(plan, cases, index, source, *, check_consistency=True):
    """Missing contracts are incomplete, malformed/invented contracts are rejected."""
    policy = json.loads(plan.get('acceptance_json', '{}'))
    if not isinstance(policy, dict):
        raise ValueError('acceptance_json must be an object')
    if policy:
        if not policy.get('purposes') or any(p not in {'computation', 'operation', 'report'} for p in policy['purposes']):
            raise ValueError('Acceptance scope must declare its required purposes')
        if policy.get('invalid_input') not in {'required', 'not_applicable'} or not policy.get('scope') or not grounded(policy, index, source):
            raise ValueError('Input policy requires scope and an exact quotation from read source')
        if policy['invalid_input'] == 'required' and not policy.get('constraint'):
            raise ValueError('Required input policy must identify the input constraint')
        for check in policy.get('checks', []):
            if not grounded(check, index, source) or not check.get('id') or check.get('channel') not in {'args', 'input_files'}:
                raise ValueError('Input checks require grounded id/channel/key/pattern')
            if check['channel'] == 'args' and (type(check.get('key')) is not int or check['key'] < 0):
                raise ValueError('Argument check key must be a nonnegative index')
            if check['channel'] == 'input_files' and not isinstance(check.get('key'), str):
                raise ValueError('File check key must be a path')
            re.compile(check['pattern'])
            if check.get('mode', 'full_text') not in {'full_text', 'each_line'}:
                raise ValueError('Input check mode must be full_text or each_line')
            if check.get('mode') == 'each_line' and check['channel'] != 'input_files':
                raise ValueError('each_line applies only to fixture contents')
        checks = {check['id']: check for check in policy.get('checks', [])}
        if len(checks) != len(policy.get('checks', [])):
            raise ValueError('Input check IDs must be unique')
        operations = policy.get('operations', [])
        used, names = set(), set()
        for operation in operations:
            if not grounded(operation, index, source) or not operation.get('id') or operation['id'] in names:
                raise ValueError('Operations require unique IDs and read source evidence')
            names.add(operation['id'])
            selectors = operation.get('selector', {}).get('args')
            if not isinstance(selectors, list) or not selectors:
                raise ValueError('Operation applicability needs actual argument index/equals selectors')
            for item in selectors:
                if (set(item) != {'index', 'equals'} or type(item['index']) is not int or item['index'] < 0
                        or not isinstance(item['equals'], str) or not item['equals']
                        or item['equals'] not in operation['source_quote']):
                    raise ValueError('Operation selector must match a literal documented invocation token')
            selected = operation.get('checks')
            if not isinstance(selected, list) or not selected or not set(selected) <= checks.keys():
                raise ValueError('Each input operation must apply named input checks; no per-case exemptions')
            if not operation.get('purposes') or not set(operation['purposes']) <= set(policy['purposes']):
                raise ValueError('Operation business purposes must belong to declared scope')
            if type(operation.get('require_persistence', False)) is not bool:
                raise ValueError('require_persistence must be boolean')
            used.update(selected)
        if operations and used != checks.keys():
            raise ValueError('Every input check must be associated with an operation')
        if operations:
            for check in checks.values():
                if check['channel'] == 'input_files' and (type(check.get('argument_index')) is not int or check['argument_index'] < 0):
                    raise ValueError('File checks must bind fixture content to its /input/path argument_index')
    for case in cases:
        contract = case.get('acceptance')
        if contract is None:
            continue
        if not grounded(contract, index, source):
            raise ValueError('Case acceptance requires an exact quotation from read source')
        if contract.get('purpose') not in {'computation', 'operation', 'report', 'input_rejection'}:
            raise ValueError('Unknown acceptance purpose')
        assertion = contract.get('assertion')
        if not isinstance(assertion, dict) or not grounded(assertion, index, source):
            raise ValueError('Result assertion must have source evidence')
        required_role = {'computation': 'completion', 'operation': 'result', 'report': 'report', 'input_rejection': 'rejection'}[contract['purpose']]
        if assertion.get('role') != required_role:
            raise ValueError('Outcome assertion role must match the promised purpose: ' + required_role)
        kind = assertion.get('kind')
        if kind in {'json', 'jsonl'}:
            if kind == 'jsonl' and (type(assertion.get('record_index')) is not int or assertion['record_index'] < 0):
                raise ValueError('JSONL outcome requires a nonnegative record_index')
            if not isinstance(assertion.get('path'), list) or not assertion['path'] or not all(isinstance(p, (str, int)) for p in assertion['path']):
                raise ValueError('JSON outcome assertion requires a nonempty field path')
            values = assertion.get('allowed_values')
            if not isinstance(values, list) or not values or any(isinstance(v, (dict, list)) for v in values):
                raise ValueError('JSON outcome assertion requires scalar allowed_values')
        elif kind in {'stdout_equals', 'stderr_contains'}:
            if not isinstance(assertion.get('value'), str) or not assertion['value'].strip():
                raise ValueError('Outcome text must be nonempty')
        else:
            raise ValueError('Outcome assertion must be json/jsonl or asserted text; exit code alone is insufficient')
        if case.get('relation'):
            raise ValueError('Acceptance outcome requires a direct invocation, not a relation')
        if contract['purpose'] == 'input_rejection' and (not contract.get('violates') or not contract.get('invalid_input_reason')):
            raise ValueError('Rejection requires an identified constraint and explanation of the actual invalid input')
        # Policy is part of each locked case, so repair cannot change applicability.
        case['acceptance_policy'] = policy
    conflicts = consistency(cases) if check_consistency else []
    if conflicts:
        raise ContractConflict(conflicts)
    return policy
