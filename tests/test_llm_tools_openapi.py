import llm
import json
from llm_tools_openapi import openapi


def test_tool():
    model = llm.get_model("echo")
    chain_response = model.chain(
        json.dumps(
            {
                "tool_calls": [
                    {"name": "openapi", "arguments": {"input": "pelican"}}
                ]
            }
        ),
        tools=[openapi],
    )
    responses = list(chain_response.responses())
    tool_results = json.loads(responses[-1].text())["tool_results"]
    assert tool_results == [
        {"name": "openapi", "output": "hello pelican", "tool_call_id": None}
    ]
