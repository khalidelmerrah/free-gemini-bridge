"""Tests for the standalone auth-source discovery (v3)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gemini_cli_bridge as b

EXPORT = {
    "schema": "cockpit-tools.data-transfer",
    "accounts": {
        "platforms": {
            "antigravity": {
                "exported_data": [
                    {"email": "alice@gmail.com",
                     "refresh_token": "1//fake-alice-rt"},
                    {"email": "bob@gmail.com",
                     "refresh_token": "1//fake-bob-rt"},
                ]
            },
            "antigravity_ide": {
                "exported_data": [
                    {"email": "alice@gmail.com",
                     "refresh_token": "1//fake-alice-rt"},
                ]
            },
            "codex": {"exported_data": []},
        }
    },
}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cockpit_export_import_dedupes(self):
        exp = self.tmp / "cockpit_export.json"
        exp.write_text(json.dumps(EXPORT), encoding="utf-8")
        with patch.object(b, "REPO", self.tmp):
            found = b._discover_external_accounts()
        # alice appears in both sections — deduped to one account;
        # (a real HOME-based IDE account may also be present — ignore it)
        self.assertIn("alice@gmail.com", found)
        self.assertIn("bob@gmail.com", found)
        self.assertEqual(found["alice@gmail.com"]["source"], "cockpit-export")
        self.assertEqual(found["alice@gmail.com"]["refresh_token"], "1//fake-alice-rt")

    def test_merge_does_not_clobber_existing(self):
        reg = self.tmp / "accounts.json"
        reg.write_text(json.dumps({
            "oauth_client": {"id": "x", "secret": "y"},
            "accounts": [{"email": "alice@gmail.com",
                          "refresh_token": "1//original",
                          "source": "manual"}],
        }), encoding="utf-8")
        exp = self.tmp / "cockpit_export.json"
        exp.write_text(json.dumps(EXPORT), encoding="utf-8")
        with patch.object(b, "REGISTRY", reg), patch.object(b, "REPO", self.tmp):
            accts = b._accounts()
        # alice keeps her original token; bob is added
        self.assertEqual(accts["alice@gmail.com"]["refresh_token"], "1//original")
        self.assertEqual(accts["bob@gmail.com"]["refresh_token"], "1//fake-bob-rt")

    def test_no_export_no_crash(self):
        # IDE discovery (HOME-based) may find the real state.vscdb account;
        # the point is: absent export file -> no cockpit-export accounts, no crash.
        with patch.object(b, "REPO", self.tmp):
            found = b._discover_external_accounts()
        self.assertTrue(all(a["source"] != "cockpit-export" for a in found.values()))


if __name__ == "__main__":
    unittest.main()
