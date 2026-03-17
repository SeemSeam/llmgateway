# llmgateway

Generic async LLM gateway with shared transport, concurrency control, retry
handling, and tier-based task routing.

## Install

```bash
pip install -e ".[dev]"
```

## Config

```yaml
version: 1
provider:
  provider_type: glm
  api_style: openai_responses
  base_url: https://your-backend.example
  api_key: your-api-key
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
`tier`.

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
