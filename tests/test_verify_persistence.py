"""Le test ne doit pas viser une URL appartenant à un autre cluster."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('verify_persistence', Path(__file__).resolve().parents[1] / 'scripts/verify-persistence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TargetValidationTests(unittest.TestCase):
    def setUp(self):
        self.pods = [
            {'name': 'api-a', 'component': 'api', 'ready': True},
            {'name': 'api-b', 'component': 'api', 'ready': True},
            {'name': 'db-0', 'component': 'database', 'ready': True},
        ]

    def test_accepts_api_from_selected_context(self):
        module.validate_target({'status': 200, 'body': {'hostname': 'api-b'}}, self.pods)

    def test_rejects_other_cluster_before_mutation(self):
        with self.assertRaisesRegex(ValueError, 'URL.*contexte'):
            module.validate_target({'status': 200, 'body': {'hostname': 'api-other-cluster'}}, self.pods)

    def test_rejects_missing_replica(self):
        with self.assertRaisesRegex(ValueError, 'deux API'):
            module.validate_target({'status': 200, 'body': {'hostname': 'api-a'}}, self.pods[:1])

    def test_rejects_unavailable_api(self):
        with self.assertRaises(ValueError):
            module.validate_target({'status': 502, 'body': 'Bad Gateway'}, self.pods)


if __name__ == '__main__':
    unittest.main()
