# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and this project follows Semantic Versioning.

---

## [0.1.0] - 2026-06-20

### Added

* Initial public release of BugBee.
* AI-powered CLI wrapper for debugging command-line applications.
* Automatic traceback parsing and source code localization.
* Context-aware error analysis using DeepSeek-R1.
* Retrieval-Augmented Generation (RAG) using ChromaDB and official documentation.
* Automatic extraction of relevant code context around failures.
* SHA256-based error caching to avoid repeated LLM calls.
* Automatic code patch generation.
* Interactive patch approval workflow.
* Safe patch application with backup support.
* Validation run after patching.
* Metrics collection including:

  * Success rate
  * Auto-fix count
  * Token usage
  * Average latency
  * Cache statistics
* Configurable CLI using Typer.
* Cross-platform configuration handling.
* Lazy loading for improved CLI startup performance.
* PyPI packaging support.
* Open-source project structure.
