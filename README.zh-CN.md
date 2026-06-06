# llmgateway

[English](README.md) | [简体中文](README.zh-CN.md)

`llmgateway` 是一个轻量的异步 Python 库，用统一的运行时配置调用大语言模型。它适合被其他
Python 应用作为依赖引入，让应用内部只面对一套 API，同时可以在多个模型服务商之间切换。

这个项目关注请求路由和运行时行为。它不是托管服务，不提供登录流程、后台进程，也没有命令行
入口。

## 功能介绍

- 统一的异步 `Gateway` API，支持文本请求、JSON 请求、重试和批量请求。
- 支持按顺序配置多个 provider，并在失败时自动切换到后续 provider。
- 成功可用的 provider 会记录到本地 provider state，后续请求会优先尝试它。
- 支持按任务路由模型，内置 `strong`、`weak`、fallback 和任务级模型覆盖。
- 支持通过 `model_map` 把逻辑模型名映射成 provider 真实模型名。
- 支持并发上限、超时、传输重试和校验重试。
- 提供 JSON 解析辅助，可以解析纯 JSON 或 fenced JSON 响应。
- 配置文件支持从环境变量读取密钥和默认值。
- 内置 OpenAI Responses、OpenAI Chat Completions、Anthropic Messages 和 LiteLLM 风格后端。

## 安装

需要 Python 3.10 或更新版本。基础运行依赖是 `httpx` 和 `PyYAML`。

### 从 registry 安装

当 `seemseam_llmgateway` distribution 已经发布到 PyPI 或你的私有 Python registry 后，可以这样安装：

```bash
python3 -m pip install seemseam_llmgateway
```

如果 `pip` 提示找不到匹配的 distribution，说明目标 registry 里还不可见。此时请先使用下面的
GitHub 安装或本地开发安装方式，等发布完成后再切换到 registry 安装。

### 从 GitHub 安装

如果需要使用当前仓库源码，而不是等待 registry 发布，可以直接从 GitHub 安装：

```bash
python3 -m pip install "seemseam_llmgateway @ git+https://github.com/SeemSeam/llmgateway.git"
```

### 本地开发安装

从本地 checkout 安装开发环境：

```bash
git clone https://github.com/SeemSeam/llmgateway.git
cd llmgateway
python3 -m pip install -e ".[dev]"
```

LiteLLM 后端只会在配置 `api_style: litellm` 时导入 `litellm`。如果你使用这个后端，需要单独安装：

```bash
python3 -m pip install litellm
```

这个项目目前不维护 npm runtime。正常使用路径是安装 Python 包，并在 Python 代码里 import
`llmgateway`。

## 快速开始

创建用户配置文件：

```bash
mkdir -p ~/.llmgateway

# 如果当前在仓库 checkout 中：
cp llmgateway.example.yaml ~/.llmgateway/config.yaml

# 或者手动创建 ~/.llmgateway/config.yaml，内容可参考下面的最小配置。
```

把 provider 密钥放到环境变量中，不要直接写死在配置文件里：

```bash
export LLM_API_KEY_1="your-provider-api-key"
```

一个最小配置示例：

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

在 Python 中发起一次文本任务：

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

解析 JSON 响应：

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

批量运行多个任务，并共用配置里的并发限制：

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

## 配置说明

`llmgateway` 可以用 `load_runtime_spec()` 从指定路径读取配置，也可以用 `load_user_config()` 从用户
配置位置读取。

默认路径：

- 配置文件：`~/.llmgateway/config.yaml`
- provider state：`~/.llmgateway/provider-state.json`

可用环境变量：

- `LLMGATEWAY_CONFIG`：指定配置文件路径。
- `LLMGATEWAY_USER_CONFIG_DIR`：指定包含 `config.yaml` 的目录。
- `LLMGATEWAY_PROVIDER_STATE`：指定 provider-state JSON 文件路径。

用户配置里的字符串可以引用环境变量：

- `${ENV_NAME}`：读取环境变量，不存在时为空字符串。
- `${ENV_NAME:-default}`：读取环境变量，不存在时使用 `default`。
- `env:ENV_NAME`：读取环境变量。

provider 字段：

- `provider_type`：provider 标签，例如 `openai`、`anthropic`、`litellm`。
- `api_style`：可选 `responses`、`openai_responses`、`openai_chat`、`anthropic` 或 `litellm`。
- `base_url`：provider API base URL。
- `api_key`：provider API key，通常来自环境变量。
- `headers`：额外 HTTP header。
- `model_map`：把逻辑模型名映射成 provider 真实模型名。

task 字段：

- `model`：该任务直接使用的模型。
- `tier`：`strong` 或 `weak`，会从 `settings.strong_model` 和 `settings.weak_model` 解析。
- `temperature`：请求温度。
- `reasoning_effort`：兼容后端可使用的 reasoning effort 提示。
- `max_tokens`：输出 token 上限。

更多 provider 链路示例见 [llmgateway.example.yaml](llmgateway.example.yaml)。

## API 概览

多数应用只需要使用 `Gateway`：

- `run_task(task, messages)`：运行一个任务并返回文本。
- `run_task_with_retry(task, messages, validator=...)`：生成失败或校验失败时重试。
- `run_json_task(task, messages)`：返回 `JSONResult`，其中 `data` 是解析后的 JSON。
- `run_json_task_with_retry(...)`：结合校验重试和 JSON 解析。
- `run_tasks([TaskRequest, ...])`：按配置的并发上限运行多条请求，返回 `CallResult`。
- `run_tasks_with_retry(...)` 和 `run_json_tasks_with_retry(...)`：批量请求的重试版本。

如果应用自己管理配置 UI 或配置文件，也可以使用导出的底层辅助函数，例如
`runtime_spec_from_dict()`、`load_runtime_spec()`、`load_user_config()` 和 `write_user_config()`。

## 安全边界

- `llmgateway` 不创建账号，不索取 registry 凭据，也不管理 provider 账单。
- provider API key 应放在环境变量或私有本地配置文件里，不要提交真实凭据。
- prompt 和响应内容会发送给你配置的 provider endpoint。只有在 provider 和账号允许处理对应数据时，
  才发送敏感内容。
- provider state 只保存 provider 链路偏好的本地 hash 信息，不是凭据存储。
- 配置文件会决定对外请求的 API URL 和 header。不要直接信任未知来源的配置文件。

## 开发

运行测试：

```bash
PYTHONPATH=src python3 -m pytest -q
```

构建并检查包元数据：

```bash
rm -rf build dist
find . -maxdepth 1 -name '*.egg-info' -prune -exec rm -rf {} +
find src -maxdepth 1 -name '*.egg-info' -prune -exec rm -rf {} +
python3 -m build
python3 -m twine check dist/*
```

在干净虚拟环境中 smoke-test wheel：

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

## 包名

- Python distribution 名称：`seemseam_llmgateway`
- Python import 名称：`llmgateway`
- 命令行名称：无
- npm 包：当前不维护此 runtime 的 npm 包

当前包元数据版本是 [pyproject.toml](pyproject.toml) 中的 `0.1.2`。

## License

MIT。见 [LICENSE](LICENSE)。
