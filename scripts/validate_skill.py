"""Validate a skill folder. Usage: python3 scripts/validate_skill.py <path>

Checks: SKILL.md exists, frontmatter name and description exist,
name is lowercase hyphenated under 64 characters, folder name
matches skill name, and no scaffold placeholder remains.
Returns exit code 0 on pass, 1 on fail, with one line per problem.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plugins.loader import parse_frontmatter, PluginError  # noqa: E402


def validate(path):
    errors = []
    skill = os.path.join(path, "SKILL.md")
    if not os.path.isfile(skill):
        return ["missing SKILL.md"]
    with open(skill, encoding="utf-8") as f:
        text = f.read()
    try:
        frontmatter, _body = parse_frontmatter(text)
    except PluginError as exc:
        return [str(exc)]
    name = frontmatter.get("name", "")
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", name):
        errors.append("invalid skill name: %r" % name)
    if name and os.path.basename(os.path.normpath(path)) != name:
        errors.append("folder name does not match skill name")
    if not frontmatter.get("description"):
        errors.append("missing description in frontmatter")
    for placeholder in ("TODO", "Lorem ipsum", "[insert", "XXX"):
        if placeholder in text:
            errors.append("scaffold placeholder found: %s" % placeholder)
    return errors


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: validate_skill.py <path>")
        sys.exit(2)
    problems = validate(sys.argv[1])
    if problems:
        for problem in problems:
            print("FAIL:", problem)
        sys.exit(1)
    print("OK")
