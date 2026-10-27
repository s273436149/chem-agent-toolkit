"""Pure pre-execution contract coverage, migrated from d5b77dc; no runtime approval."""
import re

def business_args(tool, case):
    """Only the configured user entrypoint, never an environment/test runner."""
    if case.get('relation') or case.get('layer') == 'environment':
        return None
    args = case.get('args', [])
    if not case.get('entrypoint'):
        return args
    entry = tool['entrypoint']
    if case['entrypoint'] == entry[0] and args[:len(entry)-1] == entry[1:]:
        return args[len(entry)-1:]
    return None


def operation_matches(operation, args):
    return args is not None and all(
        item['index'] < len(args) and args[item['index']] == item['equals']
        for item in operation['selector']['args'])


def input_check(case, check, args):
    """None means absent/unbound material, not a demonstrated invalid value."""
    try:
        if check['channel'] == 'args':
            value = args[check['key']]
        else:
            value = case.get('input_files', {})[check['key']]
            if 'argument_index' in check and args[check['argument_index']] != '/input/' + check['key']:
                return None
    except (IndexError, KeyError, TypeError):
        return None
    values = value.splitlines() if check.get('mode') == 'each_line' else [value]
    return bool(values) and all(re.fullmatch(check['pattern'], item) is not None for item in values)


def acceptance_coverage(tool, cases, observations=None):
    """No output-string heuristics: coverage and success follow locked contracts."""
    if tool.get('acceptance_version') != 2:
        return {'version': 1, 'complete': False, 'reasons': ['Legacy evidence; current acceptance not evaluated']}
    policy = tool.get('acceptance_policy', {})
    reasons = []
    supported = [c for c in cases if c.get('oracle_status') == 'supported' and c.get('acceptance')]
    direct = [c for c in supported if business_args(tool, c) is not None]
    positive = [c for c in direct if c['acceptance']['purpose'] in {'computation', 'operation', 'report'}
                and c.get('expected_exit', 0) == 0 and not c.get('relation')
                and not any(a in {'--help', '--version', '-h', '-V'} for a in c['args'])]
    negative = [c for c in direct if c['acceptance']['purpose'] == 'input_rejection']
    checks = policy.get('checks', [])
    operations = policy.get('operations', [])
    def routes(case):
        return [op for op in operations if operation_matches(op, business_args(tool, case))]
    def applicable(case):
        if not operations:
            return checks
        matched = routes(case)
        if len(matched) != 1:
            return None
        return [check for check in checks if check['id'] in matched[0]['checks']]
    def accepts(case, check):
        return input_check(case, check, business_args(tool, case))
    def valid(case):
        selected = applicable(case)
        return selected is not None and all(accepts(case, check) is True for check in selected)
    positive = [c for c in positive if valid(c)]
    completed_negative = [c for c in direct if c['acceptance']['purpose'] in {'computation', 'operation', 'report'}
                          and c.get('expected_exit', 0) != 0 and valid(c)]
    def outcome(case):
        assertion = case['acceptance']['assertion']
        return (case.get('expected_exit', 0), {k:v for k,v in assertion.items()
                if k not in {'source_path', 'source_quote', 'role'}})
    def rejects(case, check):
        selected = applicable(case)
        return (case['acceptance'].get('violates') == check['id'] and selected is not None
                and check in selected and accepts(case, check) is False
                and all(outcome(case) != outcome(normal) for normal in positive))
    if not positive:
        reasons.append('No grounded normal input with a result assertion')
    if not policy.get('purposes') or not set(policy['purposes']) <= {c['acceptance']['purpose'] for c in positive}:
        reasons.append('Declared purposes are not covered by grounded normal cases')
    if policy.get('invalid_input') == 'required':
        if not checks:
            reasons.append('Input constraint lacks a checkable fixture predicate')
        for check in checks:
            matching = [c for c in negative if rejects(c, check)]
            if not matching:
                reasons.append('Missing actual invalid-input rejection: ' + check['id'])
    elif policy.get('invalid_input') != 'not_applicable' or not policy.get('source_quote') or not policy.get('scope'):
        reasons.append('Input applicability not grounded')
    elif any(c.get('args') or c.get('input_files') for c in positive):
        reasons.append('Not-applicable exemption only supports operations without supplied user input')
    operation_coverage = {}
    for operation in operations:
        normal = [c for c in positive if operation_matches(operation, business_args(tool, c))]
        rejected = [c for c in negative if operation_matches(operation, business_args(tool, c))]
        missing = []
        if not normal or not set(operation['purposes']) <= {c['acceptance']['purpose'] for c in normal}:
            missing.append('normal business purpose')
        if operation.get('require_persistence') and not any(c.get('output_file') and not c.get('capture_stdout') for c in normal):
            missing.append('persisted output')
        for check in checks:
            if check['id'] in operation['checks'] and not any(
                    rejects(c, check) for c in rejected):
                missing.append('rejection for ' + check['id'])
        operation_coverage[operation['id']] = {'normal_cases': [c['name'] for c in normal], 'missing': missing}
        reasons.extend('Operation ' + operation['id'] + ' missing ' + item for item in missing)
    # file_io remains a persistence obligation independently of which example is selected.
    if tool.get('behavior', {}).get('file_io') and not any(c.get('output_file') and not c.get('capture_stdout') for c in positive):
        reasons.append('No grounded normal persisted-output case for declared file IO')
    if observations is not None:
        passed = {c['name'] for c in observations if c['status'] == 'passed'}
        required = positive + negative + completed_negative
        if any(c['name'] not in passed for c in required):
            reasons.append('Required acceptance cases did not pass')
    return {'version': 2, 'complete': not reasons, 'reasons': reasons,
            'normal_cases': [c['name'] for c in positive],
            'operations': operation_coverage,
            'completed_negative_cases': [c['name'] for c in completed_negative],
            'purposes': sorted({c['acceptance']['purpose'] for c in positive}),
            'scientific_correctness': 'not_evaluated'}


def forwarded_args(tool, case):
    return business_args(tool, case)


class NoUsageCase(ValueError):
    """A valid contract may still lack a selectable normal invocation."""


def select_usage_case(tool,cases):
    candidates = [(c, forwarded_args(tool, c)) for c in cases if c.get("oracle_status") == "supported"]
    candidates = [(c, args) for c, args in candidates if c.get('expected_exit', 0) == 0]
    if tool.get('acceptance_version') == 2:
        normal = acceptance_coverage(tool, cases)['normal_cases']
        candidates = [(c, args) for c, args in candidates if c['name'] in normal]
    candidates = [(c, args) for c, args in candidates if args is not None and
                  (args or (tool.get('acceptance_version') == 2 and tool.get('acceptance_policy', {}).get('invalid_input') == 'not_applicable'))
                  and not any(a in {"--help", "--version", "-V", "-h"} for a in args)]
    if not candidates:
        raise NoUsageCase("No supported, directly invocable usage example; add a test exercising the configured entrypoint with real input/output")
    candidates.sort(key=lambda item: (item[0].get("expected_exit", 0) != 0, not item[0].get("output_file")))
    return candidates[0]
