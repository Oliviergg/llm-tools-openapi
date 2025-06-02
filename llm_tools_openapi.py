import llm
import requests
import json
import yaml
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse


class OpenAPIToolbox(llm.Toolbox):
    """
    A toolbox that dynamically creates tools from an OpenAPI specification.
    """
    
    def __init__(self, openapi_url: str, args: Optional[List[str]] = None):
        self.openapi_url = openapi_url
        self.args = args or []
        self.spec = None
        self.base_url = None
        self.session = None
        
    def _fetch_openapi_spec(self) -> Dict[str, Any]:
        """Fetch and parse the OpenAPI specification."""
        response = requests.get(self.openapi_url)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '')
        text = response.text
        
        # Parse based on content type or file extension
        if 'yaml' in content_type or self.openapi_url.endswith(('.yaml', '.yml')):
            return yaml.safe_load(text)
        else:
            return json.loads(text)
    
    def _extract_base_url(self, spec: Dict[str, Any]) -> str:
        """Extract the base URL from the OpenAPI spec."""
        # OpenAPI 3.0+ uses servers array
        if 'servers' in spec and spec['servers']:
            url = spec['servers'][0]['url']
            if url.startswith('/'):
                parsed = urlparse(self.openapi_url)
                return f"{parsed.scheme}://{parsed.netloc}{url}"
            else:
                return url
    
        # OpenAPI 2.0 (Swagger) uses host, basePath, and schemes
        elif 'host' in spec:
            scheme = 'https'
            if 'schemes' in spec and spec['schemes']:
                scheme = spec['schemes'][0]
            base_path = spec.get('basePath', '')
            return f"{scheme}://{spec['host']}{base_path}"
        
        # Fallback: try to extract from the OpenAPI URL
        else:
            parsed = urlparse(self.openapi_url)
            return f"{parsed.scheme}://{parsed.netloc}"
    
    def _resolve_reference(self, ref: str) -> Dict[str, Any]:
        """Resolve a JSON reference in the OpenAPI spec."""
        if not ref.startswith('#/'):
            return {}
        
        # Remove the '#/' prefix and split the path
        ref_path = ref[2:].split('/')
        # Navigate through the spec to find the referenced object
        current = self.spec
        for part in ref_path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}

        return current if isinstance(current, dict) else {}
    
    def _extract_parameters_from_schema(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract parameters from a schema object."""
        parameters = []
        # Handle schema reference
        if '$ref' in schema:
            schema = self._resolve_reference(schema['$ref'])

        # Extract properties from the schema
        properties = schema.get('properties', {})
        required = schema.get('required', [])

        for prop_name, prop_schema in properties.items():
            param = {
                'name': prop_name,
                'in': 'body',
                'required': prop_name in required,
                'description': prop_schema.get('description', ''),
                'schema': prop_schema
            }
            parameters.append(param)

        return parameters

    def _create_tool_function(self, path: str, method: str, operation: Dict[str, Any]):
        """Create a function for a specific API operation."""
        operation_id = operation.get('operationId', f"{method}_{path.replace('/', '_')}")
        summary = operation.get('summary', f"{method.upper()} {path}")
        description = operation.get('description', summary)
        parameters = operation.get('parameters', [])
        request_body = operation.get('requestBody', {})

        # Build input schema for llm.Tool
        input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        param_docs = []
        body_params = {}

        # Add path and query parameters
        for param in parameters:
            if param.get('$ref', False):
                param = self._resolve_reference(param['$ref'])
            param_name = param['name']
            param_in = param['in']
            param_required = param.get('required', False)
            param_description = param.get('description', '')
            param_schema = param.get('schema', {})

            # Add to input schema
            input_schema['properties'][param_name] = {
                **param_schema,
                'description': param_description
            }

            if param_required:
                input_schema['required'].append(param_name)
            param_docs.append(f"    {param_name} ({param_in}): {param_description}")

        # Add request body parameters if present
        if request_body:
            content = request_body.get('content', {})
            if 'application/json' in content:
                json_content = content['application/json']
                schema = json_content.get('schema', {})
                
                # Extract parameters from the schema
                body_parameters = self._extract_parameters_from_schema(schema)
                for body_param in body_parameters:
                    param_name = body_param['name']
                    param_required = body_param.get('required', False)
                    param_description = body_param.get('description', '')
                    param_schema = body_param.get('schema', {})

                    # Store body parameter info
                    body_params[param_name] = body_param

                    # Add to input schema
                    input_schema['properties'][param_name] = {
                        **param_schema,
                        'description': param_description
                    }

                    if param_required:
                        input_schema['required'].append(param_name)
                    param_docs.append(f"    {param_name}: {param_description}")
        
        # Create the actual function
        def api_function(**kwargs):
            """Execute the API call."""
            # Separate path, query, and body parameters
            path_params = {}
            query_params = {}
            headers = {'Accept': 'application/json'}
            body_data = {}

            for param in parameters:
                param_name = param['name']
                param_in = param['in']

                if param_name in kwargs and kwargs[param_name] is not None:
                    if param_in == 'path':
                        path_params[param_name] = kwargs[param_name]
                    elif param_in == 'query':
                        query_params[param_name] = kwargs[param_name]
                    elif param_in == 'header':
                        headers[param_name] = str(kwargs[param_name])

            # Collect body parameters
            for param_name in body_params:
                if param_name in kwargs:
                    body_data[param_name] = kwargs[param_name]

            # Build the full URL
            url_path = path
            for param_name, param_value in path_params.items():
                url_path = url_path.replace(f"{{{param_name}}}", str(param_value))
            # Join URL parts sequentially since urljoin only handles 2 parts at a time
            full_url = self.base_url +  url_path
            # Prepare request kwargs
            request_kwargs = {
                'method': method.upper(),
                'url': full_url,
                'headers': headers
            }

            if query_params:
                request_kwargs['params'] = query_params

            if body_data:
                request_kwargs['json'] = body_data
                headers['Content-Type'] = 'application/json'

            # Make the API call
            response = requests.request(**request_kwargs)
            try:
                # Try to parse as JSON first
                result = response.json()
            except:
                # Fallback to text
                result = response.text

            # Include status code in response
            return {
                'status': response.status_code,
                'data': result,
                'headers': dict(response.headers)
            }

        api_function.__name__ = operation_id
        api_function.__doc__ = f"{description}\n\nParameters:\n" + "\n".join(param_docs)
        return api_function, input_schema

    def _initialize(self):
        """Initialize the toolbox by fetching and parsing the OpenAPI spec."""
        self.spec = self._fetch_openapi_spec()
        self.base_url = self._extract_base_url(self.spec)

    def method_tools(self):
        tools = self.tools()
        yield from iter(tools) if tools else iter([])

    def tools(self) -> List[llm.Tool]:
        """Return a list of tools based on the OpenAPI spec."""
        if not self.spec:
            self._initialize()
        
        tools = []
        paths = self.spec.get('paths', {})

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                # Skip non-operation fields
                if method not in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                    continue

                # Skip if operation is not a dict (could be a reference)
                if not isinstance(operation, dict):
                    continue

                # Create a tool for this operation
                tool_function, input_schema = self._create_tool_function(path, method, operation)

                # Create the Tool object
                tool = llm.Tool(
                    name=tool_function.__name__,
                    description=tool_function.__doc__,
                    implementation=tool_function,
                    input_schema=input_schema
                )
                # print('-----------------------------------------------------------')
                # print(tool_function.__name__)
                # print(tool_function.__doc__)
                # print(json.dumps(input_schema, indent=4))
                # print('-----------------------------------------------------------')
                tools.append(tool)

        return tools


@llm.hookimpl
def register_tools(register):
    """Register the OpenAPI toolbox with LLM."""
    register(OpenAPIToolbox)