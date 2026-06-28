import os
import unittest
from pathlib import Path
from unittest import mock

from config_paths import get_db_path, resolve_project_path


class PathResolutionTests(unittest.TestCase):
    def test_resolves_relative_db_path_from_project_root(self):
        project_root = Path(__file__).resolve().parents[1]
        self.assertEqual(Path(get_db_path()), project_root / "seo_guardian.db")

    def test_resolves_relative_override_against_project_root(self):
        project_root = Path(__file__).resolve().parents[1]
        with mock.patch.dict(os.environ, {"DB_PATH": "custom.db"}, clear=False):
            self.assertEqual(Path(resolve_project_path(os.getenv("DB_PATH"))), project_root / "custom.db")


if __name__ == "__main__":
    unittest.main()
