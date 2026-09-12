from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

app = typer.Typer(add_completion=False, no_args_is_help=False, help="U1AI terminal agent")
console = Console()

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "u1"
CONFIG_FILE = CONFIG_DIR / "config.json"
MAX_TOOL_STEPS = 8

DEFAULTS = {
    "base_url": os.environ.get("U1_BASE_URL", "http://127.0.0.1:11434/v1"),
    "api_key": os.environ.get("U1_API_KEY", ""),
    "model": os.environ.get("U1_MODEL", "qwen2.5-coder:7b"),
    "workspace": os.environ.get("U1_WORKSPACE", str(Path.cwd())),
    "confirm_destructive": True,
}

SYSTEM_PROMPT = """You are U1, the U1AI terminal agent.
Work like a capable coding teammate, not a chat toy.

Operating rules:
- Inspect before editing.
- Prefer the smallest correct change.
- Work only inside the configured workspace unless the user explicitly changes it.
- Use tools when needed and never claim a tool ran unless it actually did.
- Explain results plainly and briefly.
- Do not expand authority because the model is more capable.
- Destructive or consequential shell actions require explicit human approval from the CLI.
- For multi-step work: inspect, plan briefly, execute, test, summarize.
"""

DANGEROUS_PATTERNS = (
    "rm -rf", "mkfs", "dd if=", "shutdown", "reboot", "poweroff",
    "git reset --hard", "git clean -fd", "git push --force", "drop database",
    "> /dev/", "chmod -r 777 /", "chown -r",
)


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    if os.environ.get("U1_BASE_URL"):
        cfg["base_url"] = os.environ["U1_BASE_URL"]
    if os.environ.get("U1_API_KEY"):
        cfg["api_key"] = os.environ["U1_API_KEY"]
    if os.environ.get("U1_MODEL"):
        cfg["model"] = os.environ["U1_MODEL"]
    if os.environ.get("U1_WORKSPACE"):
        cfg["workspace"] = os.environ["U1_WORKSPACE"]
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def workspace_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg["workspace"]).expanduser().resolve()


def safe_path(cfg: dict[str, Any], raw: str) -> Path:
    root = workspace_root(cfg)
    target = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {raw}") from exc
    return target


def is_dangerous(command: str) -> bool:
    low = command.lower().strip()
    return any(p in low for p in DANGEROUS_PATTERNS)


def run_shell(cfg: dict[str, Any], command: str) -> str:
    if is_dangerous(command) and cfg.get("confirm_destructive", True):
        console.print(Panel(command, title="[red]Destructive command requires approval[/red]"))
        if not Confirm.ask("Authorize this command?", default=False):
            return "DENIED by user. Command was not executed."
    try:
        cp = subprocess.run(
            command,
            cwd=workspace_root(cfg),
            shell=True,
            text=True,
            capture_output=True,
            timeout=120,
        )
        out = (cp.stdout + cp.stderr).strip()
        return f"exit={cp.returncode}\n{out[-12000:]}"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 120 seconds"


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "shell_exec",
                "description": "Run a shell command inside the configured workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a UTF-8 text file inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Create or replace a UTF-8 text file inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a workspace-relative directory.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "default": "."}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Show concise git status for the workspace.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


def execute_tool(cfg: dict[str, Any], name: str, args: dict[str, Any]) -> str:
    try:
        if name == "shell_exec":
            return run_shell(cfg, str(args["command"]))
        if name == "read_file":
            p = safe_path(cfg, str(args["path"]))
            if not p.exists():
                return f"ERROR: file not found: {args['path']}"
            return p.read_text(encoding="utf-8", errors="replace")[-20000:]
        if name == "write_file":
            p = safe_path(cfg, str(args["path"]))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(args["content"]), encoding="utf-8")
            return f"WROTE {p.relative_to(workspace_root(cfg))} ({p.stat().st_size} bytes)"
        if name == "list_files":
            p = safe_path(cfg, str(args.get("path", ".")))
            if not p.exists() or not p.is_dir():
                return f"ERROR: not a directory: {args.get('path', '.')}"
            rows = []
            for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:300]:
                kind = "dir" if child.is_dir() else "file"
                rows.append(f"{kind:4}  {child.name}")
            return "\n".join(rows)
        if name == "git_status":
            return run_shell(cfg, "git status --short --branch")
        return f"ERROR: unknown tool: {name}"
    except Exception as exc:
        return f"ERROR: {exc}"


def endpoint(cfg: dict[str, Any]) -> str:
    return cfg["base_url"].rstrip("/") + "/chat/completions"


def headers(cfg: dict[str, Any]) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        h["Authorization"] = f"Bearer {cfg['api_key']}"
    return h


def agent_turn(cfg: dict[str, Any], history: list[dict[str, Any]]) -> str:
    for _ in range(MAX_TOOL_STEPS):
        payload = {
            "model": cfg["model"],
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
            "tools": tool_schemas(),
            "tool_choice": "auto",
            "temperature": 0.2,
        }
        try:
            with httpx.Client(timeout=120) as client:
                r = client.post(endpoint(cfg), headers=headers(cfg), json=payload)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            return f"Connection error: {exc}\nCheck `u1 doctor` and your U1_BASE_URL / U1_MODEL settings."

        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return (msg.get("content") or "").strip()

        history.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            console.print(f"[cyan]tool[/cyan] {name} [dim]{json.dumps(args, ensure_ascii=False)[:240]}[/dim]")
            result = execute_tool(cfg, name, args)
            history.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "content": result,
            })
    return "Stopped after the maximum tool-step budget. Review the current state before continuing."


def banner(cfg: dict[str, Any]) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_row("[bold cyan]U1AI TERMINAL[/bold cyan]", "[dim]authority before autonomy[/dim]")
    table.add_row("workspace", str(workspace_root(cfg)))
    table.add_row("model", str(cfg["model"]))
    table.add_row("endpoint", str(cfg["base_url"]))
    console.print(Panel(table, border_style="cyan"))


@app.command()
def configure(
    base_url: str = typer.Option(None, help="OpenAI-compatible base URL, ending in /v1"),
    model: str = typer.Option(None, help="Model / agent ID"),
    workspace: str = typer.Option(None, help="Default workspace path"),
    api_key: str = typer.Option(None, help="API key; prefer U1_API_KEY env var for shared machines"),
):
    """Persist U1 CLI settings."""
    cfg = load_config()
    if base_url is not None:
        cfg["base_url"] = base_url
    if model is not None:
        cfg["model"] = model
    if workspace is not None:
        cfg["workspace"] = str(Path(workspace).expanduser().resolve())
    if api_key is not None:
        cfg["api_key"] = api_key
    save_config(cfg)
    console.print(f"[green]Saved[/green] {CONFIG_FILE}")


@app.command()
def doctor():
    """Check workspace and model endpoint health."""
    cfg = load_config()
    banner(cfg)
    root = workspace_root(cfg)
    console.print(f"workspace exists: {'[green]yes[/green]' if root.exists() else '[red]no[/red]'}")
    try:
        with httpx.Client(timeout=8) as client:
            r = client.get(cfg["base_url"].rstrip("/") + "/models", headers=headers(cfg))
        console.print(f"endpoint: [green]{r.status_code}[/green]")
    except Exception as exc:
        console.print(f"endpoint: [red]unreachable[/red] {exc}")


@app.command()
def run(task: str = typer.Argument(..., help="One-shot natural-language task")):
    """Run one natural-language agent task."""
    cfg = load_config()
    root = workspace_root(cfg)
    root.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, Any]] = [{"role": "user", "content": task}]
    answer = agent_turn(cfg, history)
    console.print(Markdown(answer or "(no response)"))


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Start the interactive U1 terminal when no subcommand is given."""
    if ctx.invoked_subcommand is not None:
        return
    cfg = load_config()
    root = workspace_root(cfg)
    root.mkdir(parents=True, exist_ok=True)
    banner(cfg)
    console.print("[dim]Commands: /help /clear /status /shell <cmd> /workspace <path> /model <id> /quit[/dim]\n")
    history: list[dict[str, Any]] = []
    while True:
        try:
            text = console.input("[bold cyan]u1 › [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not text:
            continue
        if text in {"/quit", "/exit", "exit", "quit"}:
            break
        if text == "/help":
            console.print("/clear  reset conversation\n/status show config\n/shell <cmd> run local shell\n/workspace <path> change workspace\n/model <id> change model\n/quit exit")
            continue
        if text == "/clear":
            history.clear()
            console.print("[green]conversation cleared[/green]")
            continue
        if text == "/status":
            banner(cfg)
            continue
        if text.startswith("/shell "):
            console.print(run_shell(cfg, text[7:].strip()))
            continue
        if text.startswith("/workspace "):
            cfg["workspace"] = str(Path(text[11:].strip()).expanduser().resolve())
            workspace_root(cfg).mkdir(parents=True, exist_ok=True)
            save_config(cfg)
            console.print(f"workspace → {cfg['workspace']}")
            continue
        if text.startswith("/model "):
            cfg["model"] = text[7:].strip()
            save_config(cfg)
            console.print(f"model → {cfg['model']}")
            continue

        history.append({"role": "user", "content": text})
        answer = agent_turn(cfg, history)
        history.append({"role": "assistant", "content": answer})
        console.print(Markdown(answer or "(no response)"))
        console.print()


if __name__ == "__main__":
    app()
