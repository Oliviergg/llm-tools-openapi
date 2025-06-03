# llm-tools-openapi

[![PyPI](https://img.shields.io/pypi/v/llm-tools-openapi.svg)](https://pypi.org/project/llm-tools-openapi/)
[![Changelog](https://img.shields.io/github/v/release/oliviergg/llm-tools-openapi?include_prereleases&label=changelog)](https://github.com/oliviergg/llm-tools-openapi/releases)
[![Tests](https://github.com/oliviergg/llm-tools-openapi/actions/workflows/test.yml/badge.svg)](https://github.com/oliviergg/llm-tools-openapi/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/oliviergg/llm-tools-openapi/blob/main/LICENSE)

a plugins that allow to use OpenAPI as a tools

## Installation

Install this plugin in the same environment as [LLM](https://llm.datasette.io/).
```bash
llm install llm-tools-openapi
```
## Usage

To use this with the [LLM command-line tool](https://llm.datasette.io/en/stable/usage.html):

```bash
llm --td --tool --tool 'OpenAPIToolbox(openapi_url="https://your/swagger.json")' 'question your API'
```

With the [LLM Python API](https://llm.datasette.io/en/stable/python-api.html):

```python
import llm
from llm_tools_openapi import openapi

model = llm.get_model("gpt-4.1-mini")

result = model.chain(
    "Example prompt goes here",
    tools=[openapi]
).text()
```

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:
```bash
cd llm-tools-openapi
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
llm install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```
