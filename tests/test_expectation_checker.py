"""T16: independent expected fields/evidence and fresh wording through normal intake."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

import test_review_policy


ROOT = Path(__file__).resolve().parents[1]


class ExpectationCheckerContract(unittest.TestCase):
    # Reuse network/credential guards, not the earlier step's test methods.
    setUp = test_review_policy.ReviewPolicyContract.setUp
    tearDown = test_review_policy.ReviewPolicyContract.tearDown
    run_saved = test_review_policy.ReviewPolicyContract.run_saved
    assert_route = test_review_policy.ReviewPolicyContract.assert_route

    def test_T16_paraphrase_and_independent_expectation_validation(self):
        from access_requests.expectations import check_expected

        expected = json.loads((ROOT / "tests/expectations/paraphrase-021.json").read_text())
        document = self.read_export(ROOT / "tests/fixtures/paraphrase-021-export.json")
        document = replace(document, document_id="IT-021.json")
        result = self.run_saved(document, "paraphrase-021.json")
        report = check_expected(document.message, expected, result)
        self.assertTrue(report["matches"])
        self.assertEqual(report["differences"], [])
        self.assert_route(result, "Owner")

        incomplete = deepcopy(expected)
        del incomplete["facts"]["manager"]
        with self.assertRaisesRegex(ValueError, "manager"):
            check_expected(document.message, incomplete, result)

        invented = deepcopy(expected)
        invented["evidence"]["manager"] = "My manager is Alice Example."
        with self.assertRaisesRegex(ValueError, "evidence"):
            check_expected(document.message, invented, result)

        no_evidence = deepcopy(expected)
        del no_evidence["evidence"]["manager"]
        with self.assertRaisesRegex(ValueError, "manager"):
            check_expected(document.message, no_evidence, result)

        wrong = deepcopy(result)
        wrong["extraction"]["permission"] = "admin"
        wrong["owner"] = "Security Review"
        report = check_expected(document.message, expected, wrong)
        self.assertFalse(report["matches"])
        self.assertEqual({difference["field"] for difference in report["differences"]},
                         {"permission", "owner"})
