# Architecture Overview

BugBee follows a **clean‑architecture** style that separates concerns into distinct
packages:

```
bugbee/
├─ cli/            # Typer command‑line interface
├─ parser/         # Error‑parsing utilities
├─ cache/          # JSON cache wrapper
├─ retrieval/      # ChromaDB retrieval abstraction
├─ llm/            # LLM provider protocol & implementations
├─ patcher/        # Safe auto‑fix patch application
├─ validator/      # Post‑patch validation runner
├─ metrics/        # Metrics collection & persistence
├─ config/         # Pydantic settings (env/.env/YAML)
├─ utils/          # Shared helpers (logging, timestamps, etc.)
└─ legacy.py       # Compatibility shim for the original entry point
```

### Data Flow
1. **CLI** (`bugbee.cli.main`) parses arguments and invokes the **run** workflow.
2. The **run** command executes the target program via `subprocess`. If the
   program returns a non‑zero exit code, its `stderr` is captured.
3. **Parser** extracts the source file and line number from the stack trace.
4. The sanitized error text is hashed and looked‑up in **Cache**. A cache hit
   short‑circuits the LLM step.
5. If no cache entry exists, **Retriever** pulls the top‑k relevant documents
   from the local ChromaDB store.
6. An **LLMProvider** (default HuggingFace) generates a diagnostic report and a
   suggested fix.
7. The **Patcher** creates a timestamped backup, applies the fix, and records
   the operation.
8. **Validator** re‑runs the original command; success updates the **Metrics**
   and optionally informs the user.
9. All metrics are written by **MetricsCollector** to `metrics.jsonl`.
10. The optional **legacy** module forwards calls to the old script for backward
    compatibility.

### Extensibility
* Adding a new LLM provider only requires implementing the `LLMProvider`
  protocol and referencing it in `default_provider()`.
* Supporting additional retrieval back‑ends (e.g., Pinecone) involves creating a
  new class with a `get_related_docs` method and wiring it in `bugbee.retrieval`.
* New CLI commands can be added in the `cli` package without touching the core
  business logic.
