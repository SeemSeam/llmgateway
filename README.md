# llmgateway

Generic async LLM gateway with:

- provider and task specs
- shared HTTP transport
- concurrency limits
- retry handling
- JSON result helpers
- YAML runtime config loading

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
  fallback_model: gpt-5.4
  max_concurrent: 32
  retry_max: 2
  transport_retries: 5
  timeout: 30
tasks:
  analysis:
    model: gpt-5.4
    reasoning_effort: low
  planner:
    model: gpt-5.4
    reasoning_effort: high
```

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
