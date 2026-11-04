import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SkillTest(unittest.TestCase):
    def test_all_builtin_skills_validate(self):
        for name in ("browser", "computer", "skill-creator"):
            path = os.path.join(ROOT, "plugins", name)
            result = subprocess.run(
                [sys.executable, os.path.join(ROOT, "scripts", "validate_skill.py"), path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_em_dash_in_skill_bodies(self):
        # Richardson's standing rule for his own writing, applied here
        # to the seed's user-facing skill text as well.
        for name in ("browser", "computer", "skill-creator"):
            with open(os.path.join(ROOT, "plugins", name, "SKILL.md"), encoding="utf-8") as f:
                self.assertNotIn("\u2014", f.read())


if __name__ == "__main__":
    unittest.main()
