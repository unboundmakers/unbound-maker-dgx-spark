import importlib.util
import math
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


class PersonalityTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('personality'), 'Personality controller is not packaged')
        import personality
        return personality

    def test_default_and_manual_expressions(self):
        state = self.module().PersonalityState()
        self.assertEqual(state.expression, 'natural')
        self.assertFalse(state.pose()['fangs'])
        poses = []
        for name in ('natural', 'curious', 'angry', 'natural'):
            state.select(name)
            poses.append(state.pose())
            self.assertEqual(state.pose()['fangs'], name == 'angry')
        self.assertNotEqual(poses[0], poses[1])
        self.assertNotEqual(poses[1], poses[2])
        self.assertEqual(poses[0], poses[3])
        with self.assertRaises(ValueError):
            state.select('automatic')

    def test_head_clamps_and_reset(self):
        state = self.module().PersonalityState()
        state.turn(100, -100)
        self.assertEqual(state.pose()['angles']['head'], [0., -12., 35.])
        state.select('curious')
        self.assertEqual(state.yaw, 35.)
        state.center()
        self.assertEqual(state.expression, 'curious')
        self.assertEqual(state.yaw, 0.)
        state.reset()
        self.assertEqual(state.expression, 'natural')

    def test_invalid_turn_is_atomic(self):
        state = self.module().PersonalityState()
        state.turn(5, 2)
        before = state.pose()
        for value in (True, None, '5', math.inf, math.nan):
            with self.subTest(value=value), self.assertRaises(ValueError):
                state.turn(3, value)
            self.assertEqual(state.pose(), before)

    def test_strict_profile_and_defaults(self):
        module = self.module()
        profile = module.validate_profile({'schema_version': 1, 'adapter': 'flyingcat-v1'})
        self.assertEqual(profile['default_expression'], 'natural')
        for field, value in (('schema_version', True), ('adapter', 'other'),
                             ('default_expression', 'angry'), ('automatic', True),
                             ('mass', 3), ('command', 'echo hello')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.validate_profile({'schema_version': 1, 'adapter': 'flyingcat-v1', field: value})


if __name__ == '__main__':
    unittest.main()
