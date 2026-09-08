"""Command-line entry point for azpipegen."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.syntax import Syntax

from azpipegen import __version__
from azpipegen.extract import extract
from azpipegen.render import RenderError, render

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="azpipegen",
        description="Turn a plain-English CI/CD description into an Azure Pipelines YAML file.",
    )
    parser.add_argument(
        "description",
        nargs="?",
        help='The pipeline in plain English, e.g. "Build a Python 3.11 app, run pytest, '
        'then deploy to an Azure Web App called my-api on push to main".',
    )
    parser.add_argument("--file", "-f", help="Read the description from a text file instead of the CLI arg.")
    parser.add_argument(
        "--output", "-o", help="Write the YAML to this path instead of printing it (e.g. azure-pipelines.yml)."
    )
    parser.add_argument(
        "--enhance",
        action="store_true",
        help="Ask Claude to refine the draft (requires ANTHROPIC_API_KEY). Falls back silently if unavailable.",
    )
    parser.add_argument("--version", action="version", version=f"azpipegen {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.file:
        description = open(args.file, encoding="utf-8").read().strip()
    elif args.description:
        description = args.description
    else:
        parser.print_help()
        return 1

    spec = extract(description)

    try:
        yaml_text = render(spec)
    except RenderError as exc:
        console.print(f"[bold red]Could not render a pipeline:[/bold red] {exc}")
        return 2

    if args.enhance:
        from azpipegen.enhance import enhance

        with console.status("[bold cyan]Asking Claude to refine the pipeline...[/bold cyan]"):
            improved = enhance(description, yaml_text, spec)
        if improved:
            yaml_text = improved
        else:
            console.print(
                "[yellow]--enhance requested but unavailable (no ANTHROPIC_API_KEY, or the call failed); "
                "using the deterministic draft.[/yellow]"
            )

    if spec.uncertainties and not args.enhance:
        for note in spec.uncertainties:
            console.print(f"[yellow]![/yellow] {note}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(yaml_text)
        console.print(f"[bold green]Wrote {args.output}[/bold green]")
    else:
        console.print(Syntax(yaml_text, "yaml", theme="ansi_dark", line_numbers=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
