"""Patch encoding for the plan fields whose schema type is JSON text.

Only ``acceptance_json`` and ``tests[].case_json`` are JSON text. The patch validator
encodes a structured value for exactly those, in every shape a pointer can address
(single field, one test, a whole ``/tests`` array, append), and keeps every other
field strict.
"""
import copy
import json
import unittest

from creation_pipeline.runtime import planner
from tests.pipeline.test_runtime_build import plan

CASE = {'args': ['CCCOCCC'], 'stdout_equals': '[]'}


def patch(base, path, value_json, op='replace', locked=False):
    answer = {'action': 'patch', 'requested_files': [], 'reason': 'encoding',
              'operations': [{'op': op, 'path': path, 'value_json': value_json}]}
    return planner.patch_plan(base, answer, locked)


class TextFieldEncodingTests(unittest.TestCase):
    def setUp(self):
        self.base = plan()

    def test_case_json_accepts_the_object_form_and_stores_text(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(CASE))
        stored = applied['tests'][0]['case_json']
        self.assertIsInstance(stored, str)
        self.assertEqual(json.loads(stored), CASE)
        planner.check_case(json.loads(stored))

    def test_case_json_accepts_the_double_encoded_text_form(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(json.dumps(CASE)))
        self.assertEqual(json.loads(applied['tests'][0]['case_json']), CASE)

    def test_acceptance_json_object_form_is_encoded(self):
        policy = dict(json.loads(self.base['acceptance_json']), note='example')
        applied = patch(self.base, '/acceptance_json', json.dumps(policy))
        self.assertIsInstance(applied['acceptance_json'], str)
        self.assertEqual(json.loads(applied['acceptance_json']), policy)

    def test_a_whole_tests_array_is_encoded_element_by_element(self):
        tests = copy.deepcopy(self.base['tests'])
        for test in tests:
            test['case_json'] = {'args': ['x']}
        applied = patch(self.base, '/tests', json.dumps(tests))
        for test in applied['tests']:
            self.assertIsInstance(test['case_json'], str)
            self.assertEqual(json.loads(test['case_json']), {'args': ['x']})
        planner.check_case(json.loads(applied['tests'][0]['case_json']))

    def test_one_replaced_test_object_is_encoded(self):
        test = copy.deepcopy(self.base['tests'][0])
        test['case_json'] = dict(CASE)
        applied = patch(self.base, '/tests/0', json.dumps(test))
        self.assertIsInstance(applied['tests'][0]['case_json'], str)
        self.assertEqual(json.loads(applied['tests'][0]['case_json']), CASE)

    def test_an_appended_test_is_encoded(self):
        test = copy.deepcopy(self.base['tests'][0])
        test['name'] = 'appended-case'
        test['case_json'] = dict(CASE)
        applied = patch(self.base, '/tests/-', json.dumps(test), op='add')
        self.assertEqual(applied['tests'][-1]['name'], 'appended-case')
        self.assertEqual(json.loads(applied['tests'][-1]['case_json']), CASE)

    def test_text_values_are_kept_unchanged(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(CASE))
        again = patch(applied, '/tests/0/case_json',
                      json.dumps(applied['tests'][0]['case_json']))
        self.assertEqual(again['tests'][0]['case_json'], applied['tests'][0]['case_json'])

    def test_invalid_json_text_for_a_text_field_is_an_invalid_patch(self):
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/tests/0/case_json', json.dumps('not json'))
        self.assertIn('must hold JSON text', str(caught.exception))

    def test_a_non_text_field_still_rejects_structured_values(self):
        for path, value in (('/output_contract', {'a': 1}),
                            ('/tests/0/name', {'n': 'x'}),
                            ('/tests/0/layer', ['environment'])):
            with self.assertRaises(planner.PlanningError, msg=path) as caught:
                patch(self.base, path, json.dumps(value))
            self.assertIn('is not of type', str(caught.exception), path)

    def test_locked_repairs_still_cannot_touch_tests_or_acceptance(self):
        for path in ('/tests', '/acceptance_json', '/tests/0/case_json'):
            with self.assertRaises(planner.PlanningError, msg=path) as caught:
                patch(self.base, path, json.dumps(CASE), locked=True)
            self.assertIn('locked', str(caught.exception).lower())

    def test_the_pre_lock_guard_still_sees_promised_tests(self):
        tests = [t for t in copy.deepcopy(self.base['tests'])][1:]
        with self.assertRaises(planner.PlanningError) as caught:
            patch(self.base, '/tests', json.dumps(tests))
        self.assertIn('cannot remove promised', str(caught.exception))

    def test_the_patched_plan_must_still_satisfy_the_plan_schema(self):
        applied = patch(self.base, '/tests/0/case_json', json.dumps(CASE))
        self.assertIn('tests', applied)
        # A missing required plan field is still rejected, coercion or not.
        bad = copy.deepcopy(self.base)
        bad.pop('base_image')
        with self.assertRaises(planner.PlanningError):
            patch(bad, '/tests/0/case_json', json.dumps(CASE))


if __name__ == '__main__':
    unittest.main()
