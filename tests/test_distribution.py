"""Check the source boundary and self-contained addon archives."""

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_packaged_sdk_imports_without_repository_or_installed_sdk(self):
        code = """
import importlib, pathlib, sys, types
package = types.ModuleType("addon_test")
package.__path__ = [sys.argv[1]]
sys.modules["addon_test"] = package
hub = importlib.import_module("addon_test.sdk").hub
assert pathlib.Path(hub.__file__).is_relative_to(pathlib.Path(sys.argv[1]))
assert "orbit3d_hub" not in sys.modules
event = hub.MotionEvent(1, 0, 1, 0, 0, 0, 0, 0)
assert hub.to_viewport_motion(event).tx == -0.000511
"""
        for folder, archive, prefix in (
            ("Blender", "Orbit3D-Blender.zip", "orbit3d_blender"),
            ("FreeCAD", "Orbit3D-FreeCAD.zip", "Orbit3D"),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                with zipfile.ZipFile(ROOT / folder / "dist" / archive) as package:
                    package.extractall(temporary)
                result = subprocess.run(
                    [sys.executable, "-I", "-c", code, str(Path(temporary) / prefix)],
                    cwd=temporary,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_tracked_source_matches_distribution(self):
        files = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        self.assertTrue(files)
        allowed_roots = {".github", "Blender", "FreeCAD", "OrbitHub", "tests", "docs"}
        allowed_files = {
            ".gitignore",
            ".clang-format",
            "pyproject.toml",
            "LICENSE",
            "README.md",
            "SECURITY.md",
            "CHANGELOG.md",
        }
        forbidden_suffixes = {
            ".dll",
            ".dylib",
            ".so",
            ".exe",
            ".bin",
            ".pem",
            ".key",
            ".p12",
        }
        for name in files:
            path = Path(name)
            self.assertTrue(path.parts[0] in allowed_roots or name in allowed_files, name)
            self.assertNotIn(path.suffix.lower(), forbidden_suffixes, name)

    def test_addon_archives_include_sdk_and_license(self):
        for folder, archive, prefix in (
            ("Blender", "Orbit3D-Blender.zip", "orbit3d_blender"),
            ("FreeCAD", "Orbit3D-FreeCAD.zip", "Orbit3D"),
        ):
            with zipfile.ZipFile(ROOT / folder / "dist" / archive) as package:
                names = package.namelist()
                self.assertIn(prefix + "/LICENSE", names)
                self.assertIn(prefix + "/orbit3d_hub/client.py", names)
                self.assertFalse(any(n.endswith((".dll", ".dylib", ".so")) for n in names))
                self.assertEqual(package.read(prefix + "/LICENSE"), (ROOT / "LICENSE").read_bytes())


if __name__ == "__main__":
    unittest.main()
