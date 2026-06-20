"""bugbee.ui
~~~~~~~~~~~~

Centralised user-facing reporting for the BugBee CLI.

Every ``log.info(...)`` / ``log.debug(...)`` / ``typer.echo(...)`` call that
used to be scattered through ``bugbee.cli.main`` now lives here, behind a
single ``UI`` class. This keeps two concerns cleanly separated:

* ``bugbee.utils.logging`` – plain structured logging (file / stdout,
  DEBUG / INFO / WARNING / ERROR) for diagnostics, CI logs, and bug
  reports.
* ``bugbee.ui`` (this module) – everything a *human* actually sees:
  spinners while work happens, colored status lines, a syntax-friendly
  panel for the AI's analysis, tables for config/doctor output, and a
  confirmation prompt for applying fixes.

``main.py`` only ever talks to the module-level ``ui`` singleton, e.g.::

    from bugbee.ui import ui

    ui.command_failed()
    with ui.spinner("Consulting the model…"):
        result = default_provider().generate(prompt)
    ui.show_analysis(result)

This makes the command pipeline read like a checklist of steps instead of
being interleaved with logging boilerplate, and it makes the presentation
layer trivial to swap out later (e.g. a ``--quiet`` or ``--json`` mode just
means dropping in a different ``UI`` implementation).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.rule import Rule
from rich.status import Status
from rich.table import Table
from rich.theme import Theme

from bugbee.utils.logging import get_logger

_log = get_logger(__name__)

_THEME = Theme(
    {
        "bugbee.brand": "bold magenta",
        "bugbee.success": "bold green",
        "bugbee.error": "bold red",
        "bugbee.warning": "bold yellow",
        "bugbee.info": "cyan",
        "bugbee.muted": "dim",
        "bugbee.path": "bold blue",
    }
)


class UI:
    """Single point of contact for everything printed to the terminal.

    Every method here pairs a structured log call (for diagnostics) with a
    short, friendly line of console output (for humans). Methods are named
    after pipeline *events* rather than log levels, so call sites in
    ``main.py`` read declaratively, e.g. ``ui.cache_hit()`` instead of
    ``log.info("Cache hit – using previously generated response.")``.
    """

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console(theme=_THEME, highlight=False)
        self.err_console = Console(theme=_THEME, stderr=True, highlight=False)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------
    def banner(self, version: str) -> None:
        self.console.print(
            Panel.fit(
                f"[bugbee.brand]\U0001F41D  BugBee[/] [bugbee.muted]v{version}[/]\n"
                "[bugbee.muted]AI-powered CLI debugger & auto-repair[/]",
                border_style="magenta",
            )
        )

    @contextmanager
    def spinner(self, message: str) -> Iterator[Status]:
        """Show a spinner + *message* for the duration of the ``with`` block."""
        _log.debug(message)
        with self.console.status(f"[bugbee.info]{message}[/]", spinner="dots") as status:
            yield status

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------
    def running_command(self, command: List[str]) -> None:
        cmd = " ".join(command)
        _log.info(f"Running command: {cmd}")
        self.console.print(Rule(f"[bugbee.muted]$ {cmd}[/]", style="dim"))

    def command_succeeded(self) -> None:
        _log.info("Command succeeded – no analysis needed.")
        self.console.print("[bugbee.success]\u2713 Command succeeded — nothing to debug.[/]")

    def command_failed(self) -> None:
        _log.warning("Command failed – analyzing error.")
        self.console.print(
            "[bugbee.error]\u2717 Command failed.[/] [bugbee.muted]Analyzing the error…[/]"
        )

    # ------------------------------------------------------------------
    # Error parsing / caching
    # ------------------------------------------------------------------
    def location_found(self, file_path: str, line_number: int) -> None:
        _log.debug(f"Extracted location: {file_path}:{line_number}")
        self.console.print(
            f"[bugbee.info]\U0001F4CD Located error at[/] [bugbee.path]{file_path}:{line_number}[/]"
        )

    def location_not_found(self) -> None:
        _log.debug("Could not determine source location from stderr.")
        self.console.print("[bugbee.warning]\u26A0 Could not determine the source location.[/]")

    def cache_hit(self) -> None:
        _log.info("Cache hit – using previously generated response.")
        self.console.print(
            "[bugbee.info]\u26A1 Cache hit[/] [bugbee.muted]— reusing a previous analysis.[/]"
        )

    def cache_miss(self) -> None:
        _log.info("Cache miss – invoking LLM.")
        self.console.print("[bugbee.muted]No cached fix found — asking the model…[/]")

    def cache_cleared(self) -> None:
        _log.info("Cache cleared.")
        self.console.print("[bugbee.success]\u2713 Cache cleared.[/]")

    def retrieval_stats(self, top_score: float, avg_score: float) -> None:
        _log.debug(f"Retrieval scores — top: {top_score}, avg: {avg_score}")

    # ------------------------------------------------------------------
    # LLM analysis
    # ------------------------------------------------------------------
    def show_analysis(self, content: str) -> None:
        self.console.print(
            Panel(content, title="\U0001F916 AI Analysis", border_style="cyan", expand=True)
        )

    # ------------------------------------------------------------------
    # Patch / auto-fix
    # ------------------------------------------------------------------
    def confirm_fix(self, auto_yes: bool) -> bool:
        if auto_yes:
            return True
        return Confirm.ask("[bold]Apply suggested fix?[/]", console=self.console, default=False)

    def applying_patch(self, file_path: str, line_number: int) -> None:
        _log.info(f"Applying patch to {file_path} at line {line_number}")
        self.console.print(
            f"[bugbee.info]\U0001F527 Applying patch to[/] [bugbee.path]{file_path}:{line_number}[/]…"
        )

    def patch_applied(self) -> None:
        _log.info("Patch applied successfully.")
        self.console.print("[bugbee.success]\u2713 Patch applied successfully.[/]")

    def patch_not_applied(self) -> None:
        _log.warning("Patch could not be applied – error line not found.")
        self.console.print(
            "[bugbee.warning]\u26A0 Patch could not be applied — error line not found.[/]"
        )

    def patch_error(self, exc: Exception) -> None:
        _log.error(f"Patch application failed: {exc}")
        self.console.print(f"[bugbee.error]\u2717 Patch application failed:[/] {exc}")

    def auto_fix_declined(self) -> None:
        _log.info("Auto-fix declined or no source file identified.")
        self.console.print("[bugbee.muted]No changes were made.[/]")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validation_passed(self) -> None:
        _log.info("Validation succeeded after patch.")
        self.console.print("[bugbee.success]\u2713 Validation succeeded after patch.[/]")

    def validation_failed(self) -> None:
        _log.warning("Validation failed after applying the patch.")
        self.console.print(
            "[bugbee.warning]\u26A0 Validation failed after applying the patch.[/]"
        )

    # ------------------------------------------------------------------
    # Misc commands
    # ------------------------------------------------------------------
    def config_table(self, values: Dict[str, Any]) -> None:
        table = Table(title="BugBee Configuration", border_style="magenta")
        table.add_column("Setting", style="bold")
        table.add_column("Value", style="bugbee.muted")
        for name, value in values.items():
            table.add_row(name, str(value))
        self.console.print(table)

    def doctor_start(self) -> None:
        self.console.print("[bugbee.info]Running BugBee doctor…[/]")

    def doctor_result(self, missing: List[str]) -> None:
        if missing:
            _log.warning(f"Missing dependencies: {', '.join(missing)}")
            self.console.print(
                f"[bugbee.error]\u2717 Missing dependencies:[/] {', '.join(missing)}"
            )
        else:
            _log.info("All dependencies present.")
            self.console.print("[bugbee.success]\u2713 All good![/]")

    def version(self, version: str) -> None:
        self.console.print(f"[bugbee.brand]bugbee[/] [bugbee.muted]{version}[/]")

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------
    def summary(self, *, fix_applied: bool, returncode: int) -> None:
        if fix_applied:
            self.console.print(Rule(style="green"))
            self.console.print("[bugbee.success]Done — fix applied.[/]")
        else:
            self.console.print(Rule(style="red"))
            self.console.print(
                f"[bugbee.error]Done — no fix applied (exit code {returncode}).[/]"
            )


# Module-level singleton so call sites can simply do ``ui.cache_hit()``.
ui = UI()