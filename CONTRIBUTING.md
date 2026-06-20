# Contributing to BugBee

First off, thank you for considering contributing to BugBee!

BugBee is an open-source AI-powered CLI debugging assistant, and contributions of all sizes are welcome.

---

# Reporting Bugs

If you discover a bug, please open a GitHub Issue.

Include:

* BugBee version
* Python version
* Operating system
* Command executed
* Error message
* Expected behavior
* Actual behavior

---

# Suggesting Features

Feature requests are welcome.

Before opening a new issue:

* Check existing issues.
* Clearly describe the problem.
* Explain why the feature would benefit BugBee users.

---

# Development Setup

Clone the repository:

```bash
git clone https://github.com/KurmadasuPranav7/bugbee.git

cd bugbee
```

Create a virtual environment:

```bash
uv venv

source .venv/bin/activate
```

Install dependencies:

```bash
uv sync
```

Run BugBee:

```bash
bugbee --help
```

---

# Running Tests

```bash
pytest
```

---

# Code Style

Please follow:

* Black
* Ruff
* Type hints
* Clear docstrings
* Small focused commits

Run before submitting:

```bash
black .

ruff check .

pytest
```

---

# Pull Requests

Before opening a PR:

* Ensure all tests pass.
* Keep pull requests focused.
* Update documentation when necessary.
* Add tests for new features whenever possible.

---

# Project Roadmap

Upcoming milestones include:

* Multi-provider LLM support
* Framework-aware retrieval
* AST-based patching
* VS Code extension
* Intelligent rollback
* Plugin architecture

---

Thank you for helping make BugBee better!
