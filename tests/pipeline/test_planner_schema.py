"""Field documentation must not mutate shared schema primitives."""
import copy
import json
from pathlib import Path
import unittest

from creation_pipeline.runtime import planner


def annotations(value, path=''):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'description' and isinstance(child, str):
                result[path + '/description'] = child
            else:
                result.update(annotations(child, path + '/' + key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            result.update(annotations(child, path + '/' + str(i)))
    return result


class PlannerSchemaTests(unittest.TestCase):
    def test_acceptance_documentation_is_only_on_intended_nodes(self):
        self.assertEqual(annotations(planner.PLAN_SCHEMA), {
            '/properties/plan/properties/acceptance_json/description': planner.ACCEPTANCE_SPEC})
        self.assertEqual(annotations(planner.PATCH_SCHEMA), {'/description': planner.ACCEPTANCE_SPEC})
        self.assertEqual(planner.S, {'type': 'string'})

    def test_acceptance_node_is_independent(self):
        schema = copy.deepcopy(planner.PLAN_SCHEMA)
        target = schema['properties']['plan']['properties']['acceptance_json']
        target['description'] = 'changed only here'
        self.assertNotIn('description', schema['properties']['requested_files']['items'])
        self.assertNotIn('description', schema['properties']['plan']['properties']['base_image'])

    def test_exact_baseline_except_misdirected_annotations(self):
        root = Path(__file__).resolve().parents[2] / 'validation/planner-schema-isolation/before'
        for name, current, keep in [
            ('plan', planner.PLAN_SCHEMA, '/properties/plan/properties/acceptance_json/description'),
            ('patch', planner.PATCH_SCHEMA, '/description')]:
            baseline = json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
            for path in annotations(baseline):
                if path == keep:
                    continue
                node = baseline
                parts = path.strip('/').split('/')
                for part in parts[:-1]:
                    node = node[int(part)] if isinstance(node, list) else node[part]
                del node[parts[-1]]
            # Exact comparison preserves required, enums, types, bounds, and closed objects.
            self.assertEqual(current, baseline)
