import unittest

from adaptive_rag import evidence_supports, route_query, valid_citations


class AdaptiveRagTests(unittest.TestCase):
    def test_routes_exact_and_aggregate_questions(self):
        self.assertEqual(route_query("Was CVE-2024-1234 remediated?").mode, "exact")
        self.assertEqual(route_query("Are all findings across agencies supported?").mode, "aggregate")
        self.assertEqual(route_query("Was authenticated scanning used?").mode, "local")

    def test_rejects_unknown_citations(self):
        self.assertTrue(valid_citations(["a"], ["a", "b"]))
        self.assertFalse(valid_citations(["outside"], ["a", "b"]))

    def test_requires_evidence_support(self):
        self.assertTrue(evidence_supports("MFA is enforced for administrators", ["MFA is enforced for administrators accessing production systems."]))
        self.assertFalse(evidence_supports("The report passed all controls", ["The report lists two unresolved findings."]))


if __name__ == "__main__":
    unittest.main()
