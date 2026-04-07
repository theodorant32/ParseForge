from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parseforge.persistence.store import RequestStore
from parseforge.pipeline.orchestrator import PipelineResult, run as pipeline_run


def _c(text: str, color: str) -> str:
    return f"{color}{text}{Style.RESET_ALL}"


def _action_color(action: str) -> str:
    return {
        "match": Fore.GREEN,
        "queue": Fore.CYAN,
        "clarify": Fore.YELLOW,
        "reject": Fore.RED,
    }.get(action, Fore.WHITE)


def _status_color(status: str) -> str:
    return {
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "failed": Fore.RED,
        "skipped": Fore.BLUE,
    }.get(status, Fore.WHITE)


def _render_pretty(result: PipelineResult, verbose: bool = False) -> None:
    click.echo()
    click.echo(_c("━" * 60, Fore.MAGENTA))
    click.echo(_c("  ParseForge Pipeline Result", Fore.MAGENTA + Style.BRIGHT))
    click.echo(_c("━" * 60, Fore.MAGENTA))

    click.echo(f"  {_c('Trace ID:', Style.BRIGHT)}  {result.trace_id}")
    click.echo(f"  {_c('Input:', Style.BRIGHT)}    {result.raw_input[:80]}{'...' if len(result.raw_input) > 80 else ''}")
    click.echo(f"  {_c('Duration:', Style.BRIGHT)}  {result.total_duration_ms:.1f} ms")

    click.echo()
    click.echo(_c("  Pipeline Stages", Style.BRIGHT))
    click.echo(_c("  " + "─" * 56, Fore.WHITE))
    for sr in result.stages:
        icon = {"success": "✅", "warning": "⚠️ ", "failed": "❌", "skipped": "⏭️ "}.get(sr.status, "  ")
        color = _status_color(sr.status)
        click.echo(
            f"  {icon}  {_c(sr.stage.ljust(18), color)}"
            f"  {_c(sr.status.upper(), color)}"
            f"  {_c(f'{sr.duration_ms:.1f}ms', Fore.WHITE)}"
        )
        if verbose and sr.errors:
            for e in sr.errors:
                click.echo(f"       {_c('↳ ' + e, Fore.RED)}")
        if verbose and sr.warnings:
            for w in sr.warnings:
                click.echo(f"       {_c('↳ ' + w, Fore.YELLOW)}")

    if result.parsed_request:
        pr = result.parsed_request
        click.echo()
        click.echo(_c("  Parsed Request", Style.BRIGHT))
        click.echo(_c("  " + "─" * 56, Fore.WHITE))
        fields = [
            ("intent", pr.get("intent")),
            ("topic", pr.get("topic")),
            ("team_size", pr.get("team_size")),
            ("timeframe", pr.get("timeframe")),
            ("urgency", pr.get("urgency")),
            ("confidence", f"{pr.get('parse_confidence', 0):.0%}"),
            ("method", pr.get("parse_method")),
        ]
        for k, v in fields:
            click.echo(f"  {_c(k.ljust(14), Fore.CYAN)}  {v}")

    if result.validation_result:
        vr = result.validation_result
        click.echo()
        click.echo(_c("  Validation", Style.BRIGHT))
        click.echo(f"  Status: {_c(vr.get('status', '?').upper(), Fore.GREEN)}")
        for w in vr.get("warnings", []):
            click.echo(f"  {_c('⚠  ' + w, Fore.YELLOW)}")
        for c in vr.get("corrections", []):
            click.echo(f"  {_c('🔧 ' + c, Fore.CYAN)}")

    if result.decision:
        d = result.decision
        action_color = _action_color(d["action"])
        click.echo()
        click.echo(_c("  Decision", Style.BRIGHT))
        click.echo(_c("  " + "─" * 56, Fore.WHITE))
        click.echo(f"  {_c('Action:', Style.BRIGHT)}   {_c(d['action'].upper(), action_color + Style.BRIGHT)}")
        click.echo(f"  {_c('Priority:', Style.BRIGHT)}  {_c(d['priority'].upper(), action_color)}")
        click.echo(f"  {_c('Score:', Style.BRIGHT)}    {_c(str(d['score']) + '/100', Fore.WHITE)}")
        click.echo(f"  {_c('Reason:', Style.BRIGHT)}   {d['reason']}")
    elif result.error:
        click.echo()
        click.echo(_c(f"  Pipeline Error: {result.error['message']}", Fore.RED + Style.BRIGHT))

    click.echo(_c("━" * 60, Fore.MAGENTA))
    click.echo()


@click.group()
@click.version_option("1.0.0", prog_name="ParseForge")
def cli():
    """ParseForge — Unstructured text → structured decisions."""


@cli.command()
@click.argument("text")
@click.option("--skip-enrichment", is_flag=True, default=False, help="Skip the enrichment stage.")
@click.option("--output", type=click.Choice(["pretty", "json"]), default="pretty", show_default=True)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show stage warnings/errors.")
@click.option("--save", is_flag=True, default=False, help="Persist result to data/results.jsonl.")
@click.option("--trace-id", default=None, help="Custom trace ID for this run.")
def run(text: str, skip_enrichment: bool, output: str, verbose: bool, save: bool, trace_id: str | None):
    if text == "-":
        text = sys.stdin.read()

    logging.getLogger().setLevel(logging.ERROR if not verbose else logging.DEBUG)

    result = pipeline_run(text.strip(), skip_enrichment=skip_enrichment, trace_id=trace_id)

    if output == "json":
        click.echo(json.dumps(result.model_dump(), indent=2, default=str))
    else:
        _render_pretty(result, verbose=verbose)

    if save:
        RequestStore().save(result)
        click.echo(_c(f"  Result saved (trace_id={result.trace_id})", Fore.BLUE))

    sys.exit(0 if result.success else 1)


@cli.command()
@click.argument("fixture_file", type=click.Path(exists=True))
@click.option("--output", type=click.Choice(["pretty", "json", "summary"]), default="summary", show_default=True)
@click.option("--save", is_flag=True, default=False, help="Persist all results.")
@click.option("--skip-enrichment", is_flag=True, default=False)
def batch(fixture_file: str, output: str, save: bool, skip_enrichment: bool):
    path = Path(fixture_file)
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        cases = raw
    elif isinstance(raw, dict) and "inputs" in raw:
        cases = raw["inputs"]
    else:
        click.echo(_c("Fixture file must be a JSON array or {\"inputs\": [...]}", Fore.RED))
        sys.exit(1)

    total = len(cases)
    successes = 0
    failures = 0
    action_counts: dict[str, int] = {}

    store = RequestStore() if save else None

    click.echo(_c(f"\nRunning {total} inputs from {path.name}...\n", Fore.MAGENTA + Style.BRIGHT))

    for i, case in enumerate(cases, 1):
        if isinstance(case, str):
            text = case
            expected_action = None
        else:
            text = case.get("input", "")
            expected_action = case.get("expected_action")

        result = pipeline_run(text, skip_enrichment=skip_enrichment)
        actual_action = result.decision["action"] if result.decision else "error"

        if result.success:
            successes += 1
        else:
            failures += 1

        action_counts[actual_action] = action_counts.get(actual_action, 0) + 1

        if output == "pretty":
            _render_pretty(result)
        elif output == "json":
            click.echo(json.dumps(result.model_dump(), indent=2, default=str))
        else:
            status_icon = "✅" if result.success else "❌"
            match_icon = ""
            if expected_action:
                match_icon = " ✓" if actual_action == expected_action else f" ✗(expected {expected_action})"
            action_color = _action_color(actual_action)
            click.echo(
                f"  [{i:02d}] {status_icon}  "
                f"{_c(actual_action.upper().ljust(8), action_color)}  "
                f"{_c(f'{result.total_duration_ms:.0f}ms', Fore.WHITE)}  "
                f"{text[:55]}{'...' if len(text) > 55 else ''}"
                f"{_c(match_icon, Fore.GREEN if '✓' in match_icon else Fore.RED)}"
            )

        if store:
            store.save(result)

    click.echo()
    click.echo(_c("━" * 60, Fore.MAGENTA))
    click.echo(_c(f"  Batch Summary — {total} inputs", Style.BRIGHT))
    click.echo(_c("  " + "─" * 56, Fore.WHITE))
    click.echo(f"  {_c('Success rate:', Style.BRIGHT)}   {_c(f'{successes}/{total} ({successes/total:.0%})', Fore.GREEN)}")
    click.echo(f"  {_c('Failures:', Style.BRIGHT)}    {_c(str(failures), Fore.RED if failures else Fore.GREEN)}")
    click.echo(f"  {_c('Actions:', Style.BRIGHT)}")
    for action, count in sorted(action_counts.items()):
        click.echo(f"    {_c(action.ljust(10), _action_color(action))}  {count}")
    click.echo(_c("━" * 60, Fore.MAGENTA))


@cli.command()
@click.option("--skip-enrichment", is_flag=True, default=False)
@click.option("--verbose", "-v", is_flag=True, default=False)
def interactive(skip_enrichment: bool, verbose: bool):
    logging.getLogger().setLevel(logging.ERROR if not verbose else logging.DEBUG)

    click.echo(_c("Welcome to the ParseForge Interactive Mode", Fore.MAGENTA + Style.BRIGHT))
    click.echo(_c("Type your request, or 'exit' / 'quit' to close.\n", Fore.WHITE))

    while True:
        try:
            text = input(_c("ParseForge> ", Fore.CYAN + Style.BRIGHT))
            if text.strip().lower() in ("exit", "quit"):
                break
            if not text.strip():
                continue

            result = pipeline_run(text.strip(), skip_enrichment=skip_enrichment)
            _render_pretty(result, verbose=verbose)

        except (KeyboardInterrupt, EOFError):
            break

    click.echo(_c("\nDesk closed.", Fore.MAGENTA))


@cli.command()
@click.argument("trace_id")
@click.argument("correct_intent")
def feedback(trace_id: str, correct_intent: str):
    import subprocess

    from parseforge.layers.schema import IntentEnum

    try:
        IntentEnum(correct_intent)
    except ValueError:
        click.echo(_c(f"Invalid intent '{correct_intent}'. Available intents: {[e.value for e in IntentEnum]}", Fore.RED))
        sys.exit(1)

    store = RequestStore()
    results_path = store.log_path

    if not results_path.exists():
        click.echo(_c("No results found. Run pipeline with --save first.", Fore.RED))
        sys.exit(1)

    target_text = None
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("trace_id") == trace_id:
                target_text = record.get("raw_input")
                break

    if not target_text:
        click.echo(_c(f"Could not find trace_id {trace_id} in {results_path}", Fore.RED))
        sys.exit(1)

    train_path = Path("data/training_data.jsonl")
    with open(train_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"text": target_text, "intent": correct_intent}) + "\n")

    click.echo(_c(f"Added to training data: '{target_text}' -> {correct_intent}", Fore.GREEN))
    click.echo(_c("Triggering ML Retraining automatically...\n", Fore.CYAN))

    result = subprocess.run([sys.executable, "train.py"], capture_output=True, text=True)
    if result.returncode == 0:
        click.echo(_c("Model retrained successfully!", Fore.MAGENTA + Style.BRIGHT))
    else:
        click.echo(_c("Model retraining failed. Check train.py output:", Fore.RED))
        click.echo(result.stderr)
        sys.exit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, default=False)
def serve(host: str, port: int, reload: bool):
    try:
        import uvicorn
    except ImportError:
        click.echo(_c("uvicorn not installed. Run: pip install uvicorn", Fore.RED))
        sys.exit(1)

    click.echo(_c(f"\nStarting ParseForge API on http://{host}:{port}\n", Fore.MAGENTA + Style.BRIGHT))
    uvicorn.run(
        "parseforge.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
