# Implement skill: no auto-commit

The `implement` skill's default instructions end with "Commit your work to the current branch." In this repo, that step is overridden.

## Rule

After implementation, TDD, and `/code-review` are done, **do not run `git commit`**. Instead:

- Run `git status` / `git diff` and list the files that are staged or ready to be staged, with a one-line summary of what changed in each.
- Stop and wait for the user to explicitly ask for a commit (e.g. "commit this", "go ahead and commit").

This applies regardless of how confident the skill run was — a green test suite and a clean review are not themselves authorization to commit.
