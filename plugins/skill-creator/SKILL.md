---
name: skill-creator
description: Create or update a Codex skill with appropriately scoped instructions and any needed supporting resources.
metadata:
  short-description: Create or update a skill
---

# Skill Creator

Create skills that give an agent useful, non-obvious guidance without constraining unrelated work.

Assume the agent is already capable. Include only information that changes its decisions or improves its work. Remove generic advice, repeated instructions, speculative edge cases, and examples that do not materially clarify the task.

Preserve user intent and scope. A skill should support the requested task, not replace the user's chosen product, expand the assignment, modify unrelated configuration, or imply permission for additional external actions. Approval to complete a task does not expand its scope or execution permissions.

Match specificity to the risk. Give room to choose an approach when multiple approaches are reasonable. Use detailed steps or absolute language only when correctness, safety, permissions, or a genuinely fragile workflow requires them.

Keep discovery cheap and precise. Skill names and descriptions are available before a skill is loaded. Describe the actual capability and when it applies. Keep skills self-contained, and refer to another skill or tool only when the workflow genuinely requires it.

Disclose detail progressively. Keep purpose, essential constraints, and routing in SKILL.md. Put substantial mode-specific guidance, schemas, examples, or procedures in supporting references, and read only the references relevant to the current task.

A skill folder contains a required SKILL.md, with frontmatter name and description, and optional scripts, references, and assets, only when the task needs them. Use lowercase letters, digits, and hyphens for names, under 64 characters, and name the folder after the skill.

Validate with scripts/validate_skill.py in this seed. The validator checks frontmatter, naming, and unfinished scaffold placeholders. It does not prove that a skill makes good decisions.
