# llmgateway

[English](https://github.com/seemseam/llmgateway#readme) |
[Simplified Chinese](https://github.com/seemseam/llmgateway/blob/main/README.zh-CN.md)

`llmgateway` is a small async Python library for calling large language models
through a shared runtime configuration. It is meant to be embedded in Python
applications that need one internal API while switching between multiple model
providers.

The package focuses on request routing and runtime behavior. It does not provide
a hosted service, login flow, background daemon, or command-line application.

## Features

- A single async `Gateway` API for text, JSON, retryable, and batch requests.
- Provider chains with ordered failover. A working provider is remembered in
  local provider state and preferred on later calls.
- Task-to-model routing with `strong`, `weak`, fallback, and per-task model
  overrides.
- Model normalization through provider `model_map` values.
- Concurrency, timeout, transport retry, and validation retry controls.
- JSON helpers that parse plain or fenced JSON responses.
- Environment-variable interpolation for local configuration.
- Built-in transports for OpenAI Responses, OpenAI Chat Completions, Anthropic
  Messages, and LiteLLM-style backends.

## Install

Python 3.10 or newer is required. The runtime dependencies are `httpx` and
`PyYAML`.

### Registry Install

When the `llmgateway` distribution is available from PyPI or your private Python
index, install it with:

```bash
python3 -m pip install llmgateway
```

If `pip` reports that no matching distribution is available, use the GitHub or
local development install path below until the release is published to the
target registry.

### GitHub Install

Install directly from the repository when you need the current source before a
registry release:

```bash
python3 -m pip install "llmgateway @ git+https://github.com/seemseam/llmgateway.git"
```

### Local Development Install

From a checkout:

```bash
git clone https://github.com/seemseam/llmgateway.git
cd llmgateway
python3 -m pip install -e ".[dev]"
```

The LiteLLM transport imports `litellm` only when `api_style: litellm` is used.
Install it separately if you use that backend:

```bash
python3 -m pip install litellm
```

There is no maintained npm runtime for this project. For normal use, install the
Python package and import `llmgateway` from Python code.

## Quick Start

Create a user config file:

```bash
mkdir -p ~/.llmgateway

# From a repository checkout:
cp llmgateway.example.yaml ~/.llmgateway/config.yaml

# Or create ~/.llmgateway/config.yaml with the minimal config below.
```

Set provider credentials in the environment instead of hard-coding them in the
config file:

```bash
export LLM_API_KEY_1="your-provider-api-key"
```

A minimal config looks like this:

```yaml
version: 1

providers:
  - provider_type: openai
    api_style: responses
    base_url: ${LLM_API_BASE_URL_1:-https://api.openai.com/v1}
    api_key: ${LLM_API_KEY_1}
    headers: {}
    model_map: {}

settings:
  fallback_model: gpt-5.4-mini
  strong_model: gpt-5.4
  weak_model: gpt-5.4-mini
  strong_reasoning_effort: high
  weak_reasoning_effort: low
  max_concurrent: 8
  retry_max: 2
  transport_retries: 2
  timeout: 30

tasks:
  analysis:
    tier: weak
    max_tokens: 4000
  planner:
    tier: strong
    max_tokens: 8000
```

Run a text task from Python:

```python
import asyncio

from llmgateway import Gateway, load_user_config, runtime_spec_from_dict


async def main() -> None:
    runtime = runtime_spec_from_dict(load_user_config())
    gateway = Gateway(runtime)

    text = await gateway.run_task(
        "analysis",
        [{"role": "user", "content": "Summarize llmgateway in one sentence."}],
    )
    print(text)


asyncio.run(main())
```

Parse a JSON response:

```python
import asyncio

from llmgateway import Gateway, load_user_config, runtime_spec_from_dict


async def main() -> None:
    runtime = runtime_spec_from_dict(load_user_config())
    gateway = Gateway(runtime)

    result = await gateway.run_json_task(
        "analysis",
        [{"role": "user", "content": "Return JSON with keys: summary, risk."}],
    )
    print(result.data)


asyncio.run(main())
```

Run multiple tasks with the shared concurrency limit:

```python
import asyncio

from llmgateway import Gateway, TaskRequest, load_user_config, runtime_spec_from_dict


async def main() -> None:
    runtime = runtime_spec_from_dict(load_user_config())
    gateway = Gateway(runtime)

    results = await gateway.run_tasks(
        [
            TaskRequest(
                task="analysis",
                messages=[{"role": "user", "content": "List the main risks."}],
            ),
            TaskRequest(
                task="planner",
                messages=[{"role": "user", "content": "Draft a short plan."}],
            ),
        ]
    )

    for result in results:
        print(result.task, result.text)


asyncio.run(main())
```

## Configuration

`llmgateway` can load a config from an explicit path with `load_runtime_spec()`,
or from the user config location with `load_user_config()`.

Default locations:

- Config file: `~/.llmgateway/config.yaml`
- Provider state: `~/.llmgateway/provider-state.json`

Environment overrides:

- `LLMGATEWAY_CONFIG`: path to a config file.
- `LLMGATEWAY_USER_CONFIG_DIR`: directory that contains `config.yaml`.
- `LLMGATEWAY_PROVIDER_STATE`: path to provider-state JSON.

String values in user config can reference environment variables:

- `${ENV_NAME}` resolves to the environment value or an empty string.
- `${ENV_NAME:-default}` resolves to the environment value or `default`.
- `env:ENV_NAME` resolves to the environment value.

Provider fields:

- `provider_type`: label such as `openai`, `anthropic`, or `litellm`.
- `api_style`: one of `responses`, `openai_responses`, `openai_chat`,
  `anthropic`, or `litellm`.
- `base_url`: provider API base URL.
- `api_key`: provider API key, usually from an environment variable.
- `headers`: extra HTTP headers.
- `model_map`: maps logical model names to provider-specific model names.

Task fields:

- `model`: exact model to use for the task.
- `tier`: `strong` or `weak`; resolved through `settings.strong_model` and
  `settings.weak_model`.
- `temperature`: request temperature.
- `reasoning_effort`: optional reasoning effort hint for compatible backends.
- `max_tokens`: output token limit.

See
[llmgateway.example.yaml](https://github.com/seemseam/llmgateway/blob/main/llmgateway.example.yaml)
for a fuller multi-provider template.

## API Overview

Most applications use `Gateway`:

- `run_task(task, messages)`: return text for one task.
- `run_task_with_retry(task, messages, validator=...)`: retry when generation or
  validation fails.
- `run_json_task(task, messages)`: return a `JSONResult` with parsed `data`.
- `run_json_task_with_retry(...)`: combine validation retry and JSON parsing.
- `run_tasks([TaskRequest, ...])`: run several requests under the configured
  concurrency limit and return `CallResult` objects.
- `run_tasks_with_retry(...)` and `run_json_tasks_with_retry(...)`: batch
  variants with validation retry.

Lower-level helpers such as `runtime_spec_from_dict()`, `load_runtime_spec()`,
`load_user_config()`, and `write_user_config()` are exported for applications
that manage their own configuration UI or files.

## Safety Boundaries

- `llmgateway` does not create accounts, ask for registry credentials, or manage
  provider billing.
- Provider API keys should be supplied through environment variables or private
  local config files. Do not commit real credentials.
- Prompt and response content is sent to the configured provider endpoints.
  Avoid sending secrets unless the selected provider and account are approved
  for that data.
- Provider state stores local preference hashes for the configured provider
  chain. It is not a credential store.
- Config files control outbound API URLs and headers. Treat untrusted config as
  untrusted code-adjacent input.

## Development

Run the test suite:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Build and validate package metadata:

```bash
rm -rf build dist
find . -maxdepth 1 -name '*.egg-info' -prune -exec rm -rf {} +
find src -maxdepth 1 -name '*.egg-info' -prune -exec rm -rf {} +
python3 -m build
python3 -m twine check dist/*
```

Smoke-test a built wheel in a clean virtual environment:

```bash
python3 -m venv /tmp/llmgateway-smoke
/tmp/llmgateway-smoke/bin/python -m pip install --upgrade pip
/tmp/llmgateway-smoke/bin/python -m pip install dist/llmgateway-*.whl
/tmp/llmgateway-smoke/bin/python - <<'PY'
from llmgateway import Gateway, runtime_spec_from_dict

runtime = runtime_spec_from_dict({
    "providers": [{"provider_type": "openai", "api_style": "responses"}],
    "settings": {"strong_model": "example-model"},
    "tasks": {"analysis": {"tier": "strong"}},
})
gateway = Gateway(runtime)
print(type(gateway).__name__, runtime.task("analysis").tier)
PY
```

## Package Names

- Python distribution name: `llmgateway`
- Python import name: `llmgateway`
- Command-line name: none
- npm package: none maintained for this runtime

The current package metadata version is `0.1.2` in
[pyproject.toml](https://github.com/seemseam/llmgateway/blob/main/pyproject.toml).

## License

MIT. See [LICENSE](https://github.com/seemseam/llmgateway/blob/main/LICENSE).
