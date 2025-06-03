import llm
import requests
import json
import yaml
from typing import Any, Dict, List, Optional, Generator
from urllib.parse import urljoin, urlparse

class OpenAPIToolboxError(Exception):
    """Base exception for OpenAPI toolbox errors."""
    pass


class SpecFetchError(OpenAPIToolboxError):
    """Raised when OpenAPI specification cannot be fetched."""
    pass


class SpecParseError(OpenAPIToolboxError):
    """Raised when OpenAPI specification cannot be parsed."""
    pass


class OpenAPIToolbox(llm.Toolbox):
    """
    A toolbox that dynamically creates tools from an OpenAPI specification.
    """
    
    def __init__(self, openapi_url: str, args: Optional[List[str]] = None) -> None:
        self.openapi_url: str = openapi_url
        self.args: List[str] = args or []
        self.spec: Optional[Dict[str, Any]] = None
        self.base_url: Optional[str] = None
        self._initialized: bool = False
        
    def _fetch_openapi_spec(self) -> Dict[str, Any]:
        """Fetch and parse the OpenAPI specification."""
        try:
            response = requests.get(self.openapi_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise SpecFetchError(f"Failed to fetch OpenAPI spec from {self.openapi_url}: {e}")
        
        content_type = response.headers.get('content-type', '')
        text = response.text
        
        try:
            if 'yaml' in content_type or self.openapi_url.endswith(('.yaml', '.yml')):
                return yaml.safe_load(text)
            else:
                return json.loads(text)
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise SpecParseError(f"Failed to parse OpenAPI spec: {e}")
    
    def _validate_spec(self, spec: Dict[str, Any]) -> None:
        """Validate the OpenAPI specification has required fields."""
        if not isinstance(spec, dict):
            raise SpecParseError("OpenAPI specification must be a dictionary")
        
        if 'paths' not in spec:
            raise SpecParseError("OpenAPI specification missing 'paths' field")
        
        openapi_version = spec.get('openapi') or spec.get('swagger')
        if not openapi_version:
            raise SpecParseError("OpenAPI specification missing version field")
    
    def _extract_base_url(self, spec: Dict[str, Any]) -> str:
        """Extract the base URL from the OpenAPI spec."""
        if 'servers' in spec and spec['servers']:
            url = spec['servers'][0]['url']
            if url.startswith('/'):
                parsed = urlparse(self.openapi_url)
                return f"{parsed.scheme}://{parsed.netloc}{url}"
            else:
                return url
        elif 'host' in spec:
            scheme = 'https'
            if 'schemes' in spec and spec['schemes']:
                scheme = spec['schemes'][0]
            base_path = spec.get('basePath', '')
            return f"{scheme}://{spec['host']}{base_path}"        
        else:
            parsed = urlparse(self.openapi_url)
            return f"{parsed.scheme}://{parsed.netloc}"

    def _resolve_reference(self, ref: str) -> Dict[str, Any]:
        """Resolve a JSON reference in the OpenAPI spec."""
        if not ref.startswith('#/'):
            return {}

        ref_path = ref[2:].split('/')
        current = self.spec
        for part in ref_path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}

        return current if isinstance(current, dict) else {}
    
    def _extract_parameters_from_schema(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract parameters from a schema object."""
        parameters: List[Dict[str, Any]] = []
        if '$ref' in schema:
            schema = self._resolve_reference(schema['$ref'])

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

    def _build_operation_metadata(self, path: str, method: str, operation: Dict[str, Any]) -> tuple[str, str, str]:
        """Build operation metadata (ID, summary, description)."""
        operation_id = operation.get('operationId', f"{method}_{path.replace('/', '_')}")
        summary = operation.get('summary', f"{method.upper()} {path}")
        description = operation.get('description', summary)
        return operation_id, summary, description

    def _process_parameters(self, parameters: List[Dict[str, Any]]) -> tuple[Dict[str, Any], List[str], List[str]]:
        """Process path and query parameters from OpenAPI spec."""
        input_schema_properties = {}
        required_params = []
        param_docs = []

        for param in parameters:
            if param.get('$ref', False):
                param = self._resolve_reference(param['$ref'])

            if 'name' not in param or 'in' not in param:
                continue
                
            param_name = param['name']
            param_in = param['in']
            param_required = param.get('required', False)
            param_description = param.get('description', '')
            param_schema = param.get('schema', {})

            # Add to input schema
            input_schema_properties[param_name] = {
                **param_schema,
                'description': param_description
            }

            if param_required:
                required_params.append(param_name)
            param_docs.append(f"    {param_name} ({param_in}): {param_description}")

        return input_schema_properties, required_params, param_docs

    def _process_request_body(self, request_body: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], List[str], List[str]]:
        """Process request body parameters from OpenAPI spec."""
        body_params = {}
        input_schema_properties = {}
        required_params = []
        param_docs = []

        if not request_body:
            return body_params, input_schema_properties, required_params, param_docs

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
                input_schema_properties[param_name] = {
                    **param_schema,
                    'description': param_description
                }

                if param_required:
                    required_params.append(param_name)
                param_docs.append(f"    {param_name}: {param_description}")

        return body_params, input_schema_properties, required_params, param_docs

    def _build_request_data(self, parameters: List[Dict[str, Any]], body_params: Dict[str, Any], kwargs: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, str], Dict[str, Any]]:
        """Build request data from function arguments."""
        path_params = {}
        query_params = {}
        headers = {'Accept': 'application/json'}
        body_data = {}

        # Process standard parameters
        for param in parameters:
            # Skip parameter if it doesn't have required fields
            if 'name' not in param or 'in' not in param:
                continue
                
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

        return path_params, query_params, headers, body_data

    def _build_request_url(self, path: str, path_params: Dict[str, Any]) -> str:
        """Build the full request URL with path parameters."""
        url_path = path
        for param_name, param_value in path_params.items():
            url_path = url_path.replace(f"{{{param_name}}}", str(param_value))
        return self.base_url + url_path

    def _execute_api_request(self, method: str, url: str, headers: Dict[str, str], 
                           query_params: Dict[str, Any], body_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual API request."""
        request_kwargs = {
            'method': method.upper(),
            'url': url,
            'headers': headers,
            'timeout': 30
        }

        if query_params:
            request_kwargs['params'] = query_params

        if body_data:
            request_kwargs['json'] = body_data
            headers['Content-Type'] = 'application/json'

        try:
            response = requests.request(**request_kwargs)
            try:
                result = response.json()
            except Exception:
                result = response.text

            return {
                'status': response.status_code,
                'data': result,
                'headers': dict(response.headers)
            }
        except requests.RequestException as e:
            return {
                'status': 0,
                'data': f"Request failed: {e}",
                'headers': {}
            }

    def _create_api_function(self, path: str, method: str, parameters: List[Dict[str, Any]], 
                           body_params: Dict[str, Any]) -> callable:
        """Create the actual API function that will be called."""
        def api_function(**kwargs: Any) -> Dict[str, Any]:
            """Execute the API call."""
            path_params, query_params, headers, body_data = self._build_request_data(
                parameters, body_params, kwargs
            )
            full_url = self._build_request_url(path, path_params)
            return self._execute_api_request(method, full_url, headers, query_params, body_data)
        
        return api_function

    def _create_tool_function(self, path: str, method: str, operation: Dict[str, Any]) -> tuple:
        """Create a function for a specific API operation."""
        operation_id, summary, description = self._build_operation_metadata(path, method, operation)
        parameters = operation.get('parameters', [])
        request_body = operation.get('requestBody', {})

        param_properties, param_required, param_docs = self._process_parameters(parameters)
        
        body_params, body_properties, body_required, body_docs = self._process_request_body(request_body)

        input_schema = {
            "type": "object",
            "properties": {**param_properties, **body_properties},
            "required": param_required + body_required
        }

        all_param_docs = param_docs + body_docs

        api_function = self._create_api_function(path, method, parameters, body_params)
        
        api_function.__name__ = operation_id
        api_function.__doc__ = f"{description}\n\nParameters:\n" + "\n".join(all_param_docs)
        
        return api_function, input_schema

    def _initialize(self) -> None:
        """Initialize the toolbox by fetching and parsing the OpenAPI spec.
        
        Raises:
            SpecFetchError: If the OpenAPI spec cannot be fetched.
            SpecParseError: If the OpenAPI spec cannot be parsed or is invalid.
        """
        if self._initialized:
            return 

        try:
            self.spec = self._fetch_openapi_spec()            
            self._validate_spec(self.spec)
            self.base_url = self._extract_base_url(self.spec)            
            self._initialized = True

        except (SpecFetchError, SpecParseError):
            raise
        except Exception as e:
            raise OpenAPIToolboxError(f"Unexpected error during initialization: {e}")

    def reset(self) -> None:
        """Reset the toolbox to uninitialized state."""
        self.spec = None
        self.base_url = None
        self._initialized = False

    def method_tools(self) -> Generator[llm.Tool, None, None]:
        tools = self.tools()
        yield from iter(tools) if tools else iter([])

    def tools(self) -> List[llm.Tool]:
        """Return a list of tools based on the OpenAPI spec."""
        if not self._initialized:
            self._initialize()
        
        tools: List[llm.Tool] = []
        paths = self.spec.get('paths', {})

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method not in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                    continue

                if not isinstance(operation, dict):
                    continue

                tool_function, input_schema = self._create_tool_function(path, method, operation)

                tool = llm.Tool(
                    name=tool_function.__name__,
                    description=tool_function.__doc__,
                    implementation=tool_function,
                    input_schema=input_schema
                )
                tools.append(tool)

        return tools


@llm.hookimpl
def register_tools(register):
    """Register the OpenAPI toolbox with LLM."""
    register(OpenAPIToolbox)