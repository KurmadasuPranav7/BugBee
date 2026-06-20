# 🐝 BugBee

> **AI-powered CLI debugging assistant that automatically analyzes runtime errors, retrieves relevant documentation using RAG, and suggests or applies intelligent fixes.**

BugBee wraps your terminal commands, intercepts runtime failures, analyzes the traceback, retrieves relevant documentation from official sources, and uses an LLM to explain and optionally fix the issue.

---

## ✨ Features

* 🤖 AI-powered debugging using **DeepSeek-R1**
* 📚 Retrieval-Augmented Generation (RAG) using **ChromaDB**
* 🔍 Automatic traceback parsing
* 🧠 Context-aware code analysis
* 📖 Retrieval from official framework documentation
* ⚡ SHA256-based intelligent response caching
* 🩹 Automatic code patch generation
* ✅ Validation after applying fixes
* 📊 Metrics collection
* 💻 Cross-platform support (Windows, Linux, macOS)
* 🚀 Packaged for PyPI

---

# Architecture

```
                 User Command
                       │
                       ▼
            Execute Target Program
                       │
                       ▼
               Capture stderr
                       │
                       ▼
          Parse Traceback & Context
                       │
                       ▼
             Compute Error Hash
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
       Cache Hit             Cache Miss
            │                     │
            │             Retrieve Docs
            │                     │
            │                     ▼
            │              ChromaDB Search
            │                     │
            │                     ▼
            └────────► DeepSeek-R1 ◄─────────
                             │
                             ▼
                  AI Diagnosis + Fix
                             │
                             ▼
                 Optional Auto Patch
                             │
                             ▼
                   Validation Run
                             │
                             ▼
                        Metrics
```

---

# Installation

```bash
pip install bugbee
```

---

# Configuration

Create a `.env` file in your project.

```env
HF_TOKEN=your_huggingface_api_key
```

You can obtain a Hugging Face token from:

https://huggingface.co/settings/tokens

---

# Usage

Analyze a Python script:

```bash
bugbee run python app.py
```

Analyze any command:

```bash
bugbee run pytest
```

```bash
bugbee run uv run main.py
```

Display help:

```bash
bugbee --help
```

---

# Example

Original error

```python
name = "BugBee"

print(nmae)
```

BugBee output

```
🐝 BugBee Analysis

Root Cause
-----------
NameError: name 'nmae' is not defined

Suggested Fix
-------------

Replace

print(nmae)

with

print(name)
```

After confirmation, BugBee automatically:

* Updates the file
* Creates a backup
* Executes a validation run
* Reports success or failure

---

# How It Works

1. Execute the requested command.
2. Capture stderr output.
3. Parse traceback to identify the source file and line number.
4. Extract surrounding source code.
5. Generate a unique hash of the error.
6. Check the local cache.
7. Retrieve relevant documentation using ChromaDB.
8. Send the prompt to DeepSeek-R1.
9. Parse the structured response.
10. Display the diagnosis.
11. Optionally apply the generated fix.
12. Validate the updated program.
13. Record metrics.

---

# Technologies

* Python
* Typer
* LangChain
* ChromaDB
* Sentence Transformers
* Hugging Face
* DeepSeek-R1
* Pydantic
* Rich

---

# Metrics

BugBee records useful runtime metrics including:

* Successful analyses
* Cache hit rate
* Average latency
* Token usage
* Auto-fix count
* Validation success rate

---

# Roadmap

## v0.2

* Multiple LLM providers
* Better framework detection
* Improved retrieval pipeline

## v0.3

* AST-based patch generation
* Framework-specific fix templates
* Smarter patch validation

## v1.0

* VS Code extension
* Plugin system
* Multi-language support
* Interactive terminal UI

---

# Contributing

Contributions are welcome!

Please read **CONTRIBUTING.md** before submitting pull requests.

---

# License

Apache License 2.0

---

# Author

**Pranav Kurmadasu**

If you found BugBee useful, consider giving the repository a ⭐.
