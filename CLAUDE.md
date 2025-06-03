# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

llm-tools-openapi is a Python plugin for the [LLM command-line tool](https://llm.datasette.io/) that enables the use of OpenAPI specifications as tools for large language models. It dynamically creates tools from an OpenAPI specification, allowing LLMs to interact with APIs defined by OpenAPI specs.

## Key Components

- `OpenAPIToolbox`: Main class that fetches and parses OpenAPI specifications, then generates LLM tools for each API endpoint.
- Core functionality:
  - Fetches and validates OpenAPI specs (JSON or YAML)
  - Extracts base URLs and resolves references
  - Processes parameters and request bodies
  - Builds and executes API requests
  - Creates LLM tools that correspond to API operations

## Development Commands

### Environment Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
llm install -e '.[test]'
```

### Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v
```

### Building and Publishing

```bash
# Build the package
python -m build

# Install locally for testing
pip install -e .
```

## API Usage

The plugin can be used in two ways:

1. Command-line:
```bash
llm --tool openapi "Example prompt goes here" --tools-debug
```

2. Python API:
```python
import llm
from llm_tools_openapi import openapi

model = llm.get_model("gpt-4.1-mini")
result = model.chain(
    "Example prompt goes here",
    tools=[openapi]
).text()
```