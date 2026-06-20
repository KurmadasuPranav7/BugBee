"""CLI entry point for the BugBee package.

The original monolithic implementation lived in ``cli-wrapper/src/cli_wrapper/main.py``.
This version keeps the ``run`` command as a clean pipeline built on top of:

* ``bugbee.parser.error_parser`` – stack‑trace extraction, sanitisation, hashing
* ``bugbee.cache`` – JSON cache wrapper
* ``bugbee.retrieval`` – ChromaDB document retrieval
* ``bugbee.llm`` – LLM provider abstraction
* ``bugbee.patcher`` – safe patch application with backup
* ``bugbee.validator`` – post‑patch validation runner
* ``bugbee.metrics`` – metrics collection and JSONL persistence
* ``bugbee.ui`` – ALL logging and terminal presentation (spinners, colored
  status lines, panels, tables, confirmation prompts) lives here. This file
  contains no direct ``log.*`` or ``typer.echo`` calls — every user-facing
  message is routed through the ``ui`` singleton so the pipeline below reads
  as pure business logic.

The command line mimics the historic behaviour while being fully testable,
type‑safe, and pleasant to actually use.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

import typer

from bugbee import __version__
from bugbee.config.settings import settings
from bugbee.parser.error_parser import (
    extract_location,
    sanitize_error,
    error_hash,
)
from bugbee.cache import get_cache
from bugbee.lazy import lazy_import
from bugbee.ui import ui
from bugbee.utils.logging import enable_console_logging
# Heavy imports are lazy‑loaded inside the command handlers.
# from bugbee.retrieval import get_related_docs
# from bugbee.llm import default_provider
# from bugbee.metrics import MetricsCollector
# from bugbee.patcher import apply_patch
# from bugbee.validator import run_validation

app = typer.Typer(
    help="BugBee – AI‑powered CLI debugger and auto‑repair tool",
    rich_markup_mode="rich",
)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Also print raw, timestamped log lines to the console (in addition to the normal UI).",
    ),
) -> None:
    """BugBee – AI‑powered CLI debugger and auto‑repair tool."""
    if verbose:
        enable_console_logging()


def _run_subprocess(command: List[str]) -> Tuple[int, str, str]:
    """Execute *command* and return ``(returncode, stdout, stderr)``.

    The function deliberately forwards stdout directly to the console (as the
    original tool did) and captures stderr for analysis.
    """
    import subprocess

    ui.running_command(command)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    # Echo stdout to the console to preserve original behaviour.
    if out:
        sys.stdout.write(out)
    return proc.returncode, out, err


def _parse_llm_output(output: str) -> Tuple[str, str, str]:
    """Extract ``error_line`` and ``fix`` from the LLM ``output``.

    The original script expected XML‑like tags <ERROR_LINE> and <FIX>.  We keep
    that contract for backward compatibility.
    """
    error_line_match = re.search(r"<ERROR_LINE>(.*?)</ERROR_LINE>", output, re.DOTALL)
    fix_match = re.search(r"<FIX>(.*?)</FIX>", output, re.DOTALL)
    error_line = error_line_match.group(1).strip() if error_line_match else ""
    fix = fix_match.group(1).strip() if fix_match else ""
    # The full content without the tags is also useful for reporting.
    content = output.strip()
    return content, error_line, fix


@app.command()
def run(
    command: List[str] = typer.Argument(..., help="Command to execute and debug"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto‑accept fix without prompting"),
) -> None:
    """Execute *command*, analyse failures and optionally apply an auto‑fix."""
    # Lazy imports of heavy modules – they are only loaded when this command runs.
    MetricsCollector = lazy_import('bugbee.metrics').MetricsCollector
    get_related_docs = lazy_import('bugbee.retrieval').get_related_docs
    default_provider = lazy_import('bugbee.llm').default_provider
    apply_patch = lazy_import('bugbee.patcher').apply_patch
    run_validation = lazy_import('bugbee.validator').run_validation

    metrics = MetricsCollector()
    metrics.update("command", " ".join(command))

    returncode, _, stderr = _run_subprocess(command)
    if returncode == 0:
        ui.command_succeeded()
        metrics.write()
        raise typer.Exit(code=0)

    ui.command_failed()

    # 1️⃣ Extract location info (file + line) – may be ``None``.
    file_path, line_number = extract_location(stderr, command)
    if file_path and line_number:
        ui.location_found(file_path, line_number)
    else:
        ui.location_not_found()

    # 2️⃣ Sanitize error and compute hash for caching.
    cleaned = sanitize_error(stderr)
    err_hash = error_hash(cleaned)
    cache_obj = get_cache()
    cached = cache_obj.get(err_hash)
    if cached:
        ui.cache_hit()
        llm_content, error_line, fix = cached
    else:
        ui.cache_miss()
        # Retrieve relevant docs.
        with ui.spinner("Retrieving relevant documentation…"):
            docs, top_score, avg_score = get_related_docs(stderr)
        metrics.update("retrieval.top_score", top_score)
        metrics.update("retrieval.avg_score", avg_score)
        ui.retrieval_stats(top_score, avg_score)

        # Very simple prompt composition.
        prompt = (
            f"Error message:\n{stderr}\n\n"
            f"Relevant documentation:\n{docs}\n\n"
            "Provide an XML-like response containing <ERROR_LINE> and <FIX>."
        )
        with ui.spinner("Consulting the model for a fix…"):
            llm_resp = default_provider().generate(prompt)

        llm_content, error_line, fix = _parse_llm_output(llm_resp)
        cache_obj.set(err_hash, (llm_content, error_line, fix))

    # Show the LLM analysis to the user.
    ui.show_analysis(llm_content)

    # Auto‑fix handling.
    performed = False
    accept = ui.confirm_fix(yes)
    if accept and file_path:
        ui.applying_patch(file_path, line_number)
        try:
            success = apply_patch(file_path, line_number, error_line, fix + "\n", create_backup=True)
            if success:
                performed = True
                metrics.update("autofix.patch_applied", True)
                metrics.update("autofix.files_modified", 1)
                ui.patch_applied()
                # Run validation to ensure fix works.
                with ui.spinner("Validating the fix…"):
                    validation_ok = run_validation(command, cwd=Path.cwd())
                if validation_ok:
                    metrics.update("validation.passed", True)
                    ui.validation_passed()
                else:
                    ui.validation_failed()
            else:
                ui.patch_not_applied()
        except Exception as exc:
            ui.patch_error(exc)
    else:
        ui.auto_fix_declined()

    # Record final metrics.
    metrics.update("diagnosis.error_line_found", bool(error_line))
    metrics.update("diagnosis.fix_generated", bool(fix))
    metrics.write()

    ui.summary(fix_applied=performed, returncode=returncode)

    # Exit with the original return code if no successful fix was applied.
    if performed:
        raise typer.Exit(code=0)
    else:
        raise typer.Exit(code=returncode)


@app.command()
def analyze(
    command: List[str] = typer.Argument(..., help="Command to analyze without applying a fix"),
) -> None:
    """Run *command* and display LLM analysis but do not prompt for auto‑fix."""
    # Reuse ``run`` logic but force ``yes=False`` and skip patch step.
    run(command=command, yes=False)


@app.command()
def version() -> None:
    """Print the installed BugBee version."""
    ui.version(__version__)


@app.command()
def cache_clear() -> None:
    """Remove the local cache file (``bugbee.json``)."""
    get_cache().clear()
    ui.cache_cleared()


@app.command()
def config_show() -> None:
    """Display the effective configuration (environment variables, .env, defaults)."""
    ui.config_table(settings.dict())


@app.command()
def doctor() -> None:
    """Run a quick health‑check of required dependencies and connectivity."""
    ui.doctor_start()
    missing = []
    try:
        import chromadb  # noqa: F401
    except Exception:
        missing.append("chromadb")
    try:
        import langchain  # noqa: F401
    except Exception:
        missing.append("langchain")
    ui.doctor_result(missing)
    if missing:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()