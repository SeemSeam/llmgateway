# llmgateway

`llmgateway` is a small async Python library for routing LLM calls through one
or more providers. It provides shared runtime configuration, provider failover,
concurrency limits, retry helpers, JSON parsing helpers, and task-to-model
routing.

It is designed for applications that want one internal API while switching
between OpenAI-compatible Responses APIs, Anthropic Messages, or LiteLLM-style
backends.

## Install

After first PyPI publication is complete and verified, install the Python
package with:

```bash
python3 -m pip install llmgateway
```

After first npm publication is complete and verified, install the companion npm
package with:

```bash
npm install seemseam-llmgateway
```

The npm package is a lightweight companion for JavaScript tooling that needs
package metadata or the same default config paths. It does not implement LLM
transport and does not install the Python package automatically.

For local development from a checkout:

```bash
python3 -m pip install -e ".[dev]"
npm test
```

Python 3.10 or newer is required.

## Configuration

Create a config file such as `llmgateway.yaml`, or use the default user config
path `~/.llmgateway/config.yaml`. The environment variables
`LLMGATEWAY_CONFIG`, `LLMGATEWAY_USER_CONFIG_DIR`, and
`LLMGATEWAY_PROVIDER_STATE` can override config and provider-state locations.

See [llmgateway.example.yaml](llmgateway.example.yaml) for a larger template.
A minimal single-provider config looks like this:

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

Keep `version` in `pyproject.toml` and `package.json` synchronized before
publishing a new release. Then run the clean build and metadata checks above.

First PyPI publication should be done only after confirming the `llmgateway`
project is available on PyPI and the release owner has configured a safe
publication path. Publish with a configured API token or Trusted Publisher
environment:

```bash
python3 -m twine upload dist/*
```

After publishing, verify the released package from PyPI:

```bash
python3 -m venv /tmp/llmgateway-pypi-smoke
/tmp/llmgateway-pypi-smoke/bin/python -m pip install --upgrade pip
/tmp/llmgateway-pypi-smoke/bin/python -m pip install llmgateway
/tmp/llmgateway-pypi-smoke/bin/python - <<'PY'
import llmgateway
from llmgateway import Gateway

print(llmgateway.__name__, Gateway.__name__)
PY
```

This repository now has npm package metadata, but first npm publication still
requires release-owner action. Before first npm publication, verify that the
`seemseam-llmgateway` package name is still available, inspect the tarball
contents, and publish only from a committed release state:

```bash
npm test
npm pack --dry-run
```

First npm publication can then be done by the release owner from a clean,
committed checkout:

```bash
npm publish --access public
```

The npm package is intentionally a companion package, not a full JavaScript or
TypeScript SDK. A real JS/TS LLM gateway API should be designed before expanding
the npm runtime surface.
