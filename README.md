# llmgateway

`llmgateway` is a small async Python library for routing LLM calls through one
or more LLM providers. It provides shared runtime configuration, provider
failover, concurrency limits, retry helpers, JSON parsing helpers, and
task-to-model routing.

It is designed for Python applications that want one internal API while
switching between OpenAI-compatible Responses APIs, Anthropic Messages, or
LiteLLM-style backends.

## Install

After the PyPI package is published and verified, install it with:

```bash
python3 -m pip install llmgateway
```

For local development from a checkout:

```bash
python3 -m pip install -e ".[dev]"
```

Python 3.10 or newer is required.

There is no maintained npm package for this runtime. `llmgateway` is a Python
dependency package; npm publication is not needed for normal use.

## Configuration

Create a config file such as `llmgateway.yaml`, or use the default user config
path `~/.llmgateway/config.yaml`. The environment variables
`LLMGATEWAY_CONFIG`, `LLMGATEWAY_USER_CONFIG_DIR`, and
`LLMGATEWAY_PROVIDER_STATE` can override config and provider-state locations.

See [llmgateway.example.yaml](llmgateway.example.yaml) for a larger template. A
minimal single-provider config looks like this:

```yaml
version: 1
providers:
  - provider_type: openai
    api_style: responses
    base_url: ${LLM_API_BASE_URL:-https://api.openai.com/v1}
    api_key: ${LLM_API_KEY}
    headers: {}
    model_map: {}

settings:
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
  planning:
    tier: strong
    max_tokens: 8000
```

Values written as `${ENV_NAME}` or `${ENV_NAME:-default}` are resolved from the
environment when user config is loaded. Providers are tried in order. When a
provider succeeds, `llmgateway` records that provider in `provider-state.json`
under the user config directory and can prefer it on later requests without
rewriting `config.yaml`.

Legacy single-provider config under `provider:` is still supported, but new
configs should prefer `providers:`.

## Minimal Usage

```python
import asyncio
from pathlib import Path

from llmgateway import Gateway, load_runtime_spec


async def main() -> None:
    runtime = load_runtime_spec(Path("llmgateway.yaml"))
    gateway = Gateway(runtime)

    text = await gateway.run_task(
        "analysis",
        [{"role": "user", "content": "Summarize this in one sentence."}],
    )
    print(text)


asyncio.run(main())
```

For JSON-oriented tasks:

```python
import asyncio
from pathlib import Path

from llmgateway import Gateway, load_runtime_spec


async def main() -> None:
    runtime = load_runtime_spec(Path("llmgateway.yaml"))
    gateway = Gateway(runtime)

    result = await gateway.run_json_task(
        "analysis",
        [{"role": "user", "content": "Return JSON with a summary field."}],
    )
    print(result.data)


asyncio.run(main())
```

## Development

Run the test suite:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Build source and wheel distributions:

```bash
rm -rf build dist *.egg-info src/*.egg-info
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

## Publishing

Version `0.1.2` is the current PyPI release candidate. Publish only from a
clean, committed release state after confirming the `llmgateway` project is
available on PyPI and the release owner has configured a safe publication path.

Build and validate:

```bash
rm -rf build dist *.egg-info src/*.egg-info
python3 -m build
python3 -m twine check dist/*
```

Publish to PyPI with a configured API token or Trusted Publisher environment:

```bash
python3 -m twine upload dist/*
```

After publishing, verify the released package from PyPI:

```bash
python3 -m venv /tmp/llmgateway-pypi-smoke
/tmp/llmgateway-pypi-smoke/bin/python -m pip install --upgrade pip
/tmp/llmgateway-pypi-smoke/bin/python -m pip install llmgateway==0.1.2
/tmp/llmgateway-pypi-smoke/bin/python - <<'PY'
import llmgateway
from llmgateway import Gateway

print(llmgateway.__name__, Gateway.__name__)
PY
```
