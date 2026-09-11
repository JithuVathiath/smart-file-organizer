# Contributing

Contributions are welcome when they preserve the project's safety invariants.

1. Create a focused branch and add tests for the behavior being changed.
2. Run `python -m pytest`, branch-aware coverage, and Ruff.
3. Never add destructive defaults, silent overwrite behavior, network transmission, or personal fixtures.
4. Update the safety documentation when a filesystem behavior changes.

Bug reports should include the operating system, Python version, command, redacted plan, and expected behavior. Never attach private file contents.
