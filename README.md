# llmgateway

Generic async LLM gateway with shared transport, concurrency control, retry
handling, and tier-based task routing.

## Install

```bash
pip install -e ".[dev]"
```

## Config

See [llmgateway.example.yaml](llmgateway.example.yaml) for a copy-ready
template that supports any number of providers.

```yaml
version: 1
providers:
  - provider_type: glm
    api_style: openai_responses
    base_url: https://primary-backend.example
    api_key: your-primary-api-key
    headers: {}
    model_map: {}
  - provider_type: openai
    api_style: responses
    base_url: https://secondary-backend.example
    api_key: your-secondary-api-key
    headers: {}
    model_map: {}
settings:
  strong_model: gpt-5.4
  weak_model: gpt-5.4-mini
  strong_reasoning_effort: high
  weak_reasoning_effort: low
  max_concurrent: 32
  retry_max: 2
  transport_retries: 5
  timeout: 30
tasks:
  analysis:
    tier: weak
  planner:
    tier: strong
```

`settings` owns the concrete strong/weak model pair. `tasks` usually only need a
`tier`. `providers` are tried in order, and the gateway automatically falls back
to the next provider after the current one exhausts `settings.transport_retries`.
After a provider succeeds, the gateway records it in `provider-state.json` under
the user config directory and dynamically prioritizes it on later requests,
without rewriting `config.yaml`. Legacy single-provider config under `provider:`
is still supported.

## Usage

```python
from pathlib import Path

from llmgateway import Gateway, load_runtime_spec

runtime = load_runtime_spec(Path("llmgateway.yaml"))
gateway = Gateway(runtime)

result = await gateway.run_json_task(
    "analysis",
    [{"role": "user", "content": "Reply with JSON only."}],
)
```

## Private GitHub Install

```bash
pip install "llmgateway @ git+https://github.com/<you>/llmgateway.git"
```
