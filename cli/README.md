# U1 CLI

U1AI's terminal agent: natural-language coding and shell work with bounded local tools.

## Install locally

```bash
cd cli
python -m pip install -e .
```

Then run:

```bash
u1
```

## Configure

U1 CLI talks to any OpenAI-compatible `/v1` endpoint.

```bash
u1 configure \
  --base-url http://127.0.0.1:11434/v1 \
  --model qwen2.5-coder:7b \
  --workspace ~/projects
```

Or use environment variables:

```bash
export U1_BASE_URL=https://your-endpoint.example/v1
export U1_API_KEY=...
export U1_MODEL=your-model-id
export U1_WORKSPACE=$PWD
```

## Commands

```bash
u1                         # interactive agent shell
u1 run "inspect this repo" # one-shot task
u1 doctor                  # endpoint/workspace health check
u1 configure ...           # persist settings
```

Inside the interactive terminal:

```text
/help
/status
/clear
/shell git status
/workspace ~/projects/u1
/model your-model-id
/quit
```

## Tool boundary

The first build exposes five tools to the model:

- `list_files`
- `read_file`
- `write_file`
- `git_status`
- `shell_exec`

File access is confined to the configured workspace. Known destructive shell patterns require explicit approval before execution. This is the first CLI enforcement layer; future U1 Sentinel integration should replace the lightweight local classifier with signed action envelopes, nonce/expiry binding, distinct approval where required, and tamper-evident receipts.
