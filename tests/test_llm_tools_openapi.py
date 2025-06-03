import pytest
import json
import yaml
import os
import requests
import llm
from unittest.mock import patch, Mock, MagicMock
from llm_tools_openapi import OpenAPIToolbox, SpecFetchError, SpecParseError


class TestOpenAPISpecParsing:
    """Test suite for OpenAPI specification parsing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
        self.json_spec_path = os.path.join(self.fixtures_dir, 'petstore_openapi.json')
        self.yaml_spec_path = os.path.join(self.fixtures_dir, 'petstore_openapi.yaml')
        self.invalid_spec_path = os.path.join(self.fixtures_dir, 'invalid_openapi.json')
        
    def load_fixture(self, filename):
        """Load a test fixture file."""
        filepath = os.path.join(self.fixtures_dir, filename)
        with open(filepath, 'r') as f:
            if filename.endswith('.json'):
                return json.load(f)
            else:
                return yaml.safe_load(f)

    def test_fetch_json_spec_success(self):
        """Test successful fetching and parsing of JSON OpenAPI spec."""
        json_spec = self.load_fixture('petstore_openapi.json')
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(json_spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            spec = toolbox._fetch_openapi_spec()
            
            assert spec == json_spec
            assert spec['openapi'] == '3.0.0'
            assert spec['info']['title'] == 'Pet Store API'
            assert 'paths' in spec
            assert '/pets' in spec['paths']

    def test_fetch_yaml_spec_success(self):
        """Test successful fetching and parsing of YAML OpenAPI spec."""
        yaml_spec = self.load_fixture('petstore_openapi.yaml')
        
        with patch('requests.get') as mock_get:
            # Load the actual YAML content as text
            with open(self.yaml_spec_path, 'r') as f:
                yaml_content = f.read()
            
            mock_response = Mock()
            mock_response.text = yaml_content
            mock_response.headers = {'content-type': 'application/yaml'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.yaml')
            spec = toolbox._fetch_openapi_spec()
            
            assert spec == yaml_spec
            assert spec['openapi'] == '3.0.0'
            assert spec['info']['title'] == 'Pet Store API YAML'
            assert 'paths' in spec
            assert '/pets' in spec['paths']

    def test_yaml_detection_by_extension(self):
        """Test YAML parsing when detected by file extension."""
        yaml_spec = self.load_fixture('petstore_openapi.yaml')
        
        with patch('requests.get') as mock_get:
            with open(self.yaml_spec_path, 'r') as f:
                yaml_content = f.read()
            
            mock_response = Mock()
            mock_response.text = yaml_content
            mock_response.headers = {}  # No content-type header
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Test .yaml extension
            toolbox = OpenAPIToolbox('https://example.com/openapi.yaml')
            spec = toolbox._fetch_openapi_spec()
            assert spec == yaml_spec
            
            # Test .yml extension
            toolbox = OpenAPIToolbox('https://example.com/openapi.yml')
            spec = toolbox._fetch_openapi_spec()
            assert spec == yaml_spec

    def test_fetch_spec_request_error(self):
        """Test handling of network errors when fetching OpenAPI spec."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Connection error")
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            
            with pytest.raises(SpecFetchError) as excinfo:
                toolbox._fetch_openapi_spec()
            
            assert "Failed to fetch OpenAPI spec" in str(excinfo.value)
            assert "Connection error" in str(excinfo.value)

    def test_fetch_spec_parse_error_json(self):
        """Test handling of JSON parsing errors."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = "invalid json {"
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            
            with pytest.raises(SpecParseError) as excinfo:
                toolbox._fetch_openapi_spec()
            
            assert "Failed to parse OpenAPI spec" in str(excinfo.value)

    def test_fetch_spec_parse_error_yaml(self):
        """Test handling of YAML parsing errors."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = "invalid: yaml: [unclosed"
            mock_response.headers = {'content-type': 'application/yaml'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.yaml')
            
            with pytest.raises(SpecParseError) as excinfo:
                toolbox._fetch_openapi_spec()
            
            assert "Failed to parse OpenAPI spec" in str(excinfo.value)


class TestOpenAPISpecValidation:
    """Test suite for OpenAPI specification validation."""
    
    def test_validate_spec_success(self):
        """Test successful validation of a valid OpenAPI spec."""
        valid_spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {}
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        toolbox._validate_spec(valid_spec)  # Should not raise

    def test_validate_spec_missing_paths(self):
        """Test validation failure when 'paths' field is missing."""
        invalid_spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'}
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        
        with pytest.raises(SpecParseError) as excinfo:
            toolbox._validate_spec(invalid_spec)
        
        assert "missing 'paths' field" in str(excinfo.value)

    def test_validate_spec_missing_version(self):
        """Test validation failure when version field is missing."""
        invalid_spec = {
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {}
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        
        with pytest.raises(SpecParseError) as excinfo:
            toolbox._validate_spec(invalid_spec)
        
        assert "missing version field" in str(excinfo.value)

    def test_validate_spec_not_dict(self):
        """Test validation failure when spec is not a dictionary."""
        invalid_spec = "not a dictionary"
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        
        with pytest.raises(SpecParseError) as excinfo:
            toolbox._validate_spec(invalid_spec)
        
        assert "must be a dictionary" in str(excinfo.value)

    def test_validate_spec_swagger_version(self):
        """Test validation success with Swagger 2.0 version field."""
        swagger_spec = {
            'swagger': '2.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {}
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        toolbox._validate_spec(swagger_spec)  # Should not raise


class TestOpenAPIBaseURLExtraction:
    """Test suite for base URL extraction from OpenAPI specs."""
    
    def test_extract_base_url_openapi_3_servers(self):
        """Test base URL extraction from OpenAPI 3.0 servers array."""
        spec = {
            'openapi': '3.0.0',
            'servers': [
                {'url': 'https://api.example.com/v1'},
                {'url': 'https://staging.example.com/v1'}
            ]
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        base_url = toolbox._extract_base_url(spec)
        
        assert base_url == 'https://api.example.com/v1'

    def test_extract_base_url_relative_server(self):
        """Test base URL extraction with relative server URL."""
        spec = {
            'openapi': '3.0.0',
            'servers': [
                {'url': '/api/v1'}
            ]
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        base_url = toolbox._extract_base_url(spec)
        
        assert base_url == 'https://example.com/api/v1'

    def test_extract_base_url_swagger_2(self):
        """Test base URL extraction from Swagger 2.0 spec."""
        spec = {
            'swagger': '2.0',
            'host': 'api.example.com',
            'basePath': '/v1',
            'schemes': ['https', 'http']
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        base_url = toolbox._extract_base_url(spec)
        
        assert base_url == 'https://api.example.com/v1'

    def test_extract_base_url_swagger_2_no_schemes(self):
        """Test base URL extraction from Swagger 2.0 without schemes."""
        spec = {
            'swagger': '2.0',
            'host': 'api.example.com',
            'basePath': '/v1'
        }
        
        toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        base_url = toolbox._extract_base_url(spec)
        
        assert base_url == 'https://api.example.com/v1'

    def test_extract_base_url_fallback(self):
        """Test base URL extraction fallback to OpenAPI URL."""
        spec = {
            'openapi': '3.0.0'
        }
        
        toolbox = OpenAPIToolbox('https://example.com/api/openapi.json')
        base_url = toolbox._extract_base_url(spec)
        
        assert base_url == 'https://example.com'


class TestOpenAPIParameterProcessing:
    """Test suite for OpenAPI parameter processing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.toolbox = OpenAPIToolbox('https://example.com/openapi.json')
        self.toolbox.spec = {
            'components': {
                'schemas': {
                    'Pet': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string', 'description': 'Pet name'},
                            'tag': {'type': 'string', 'description': 'Pet tag'}
                        },
                        'required': ['name']
                    }
                }
            }
        }

    def test_process_parameters_query_and_path(self):
        """Test processing of query and path parameters."""
        parameters = [
            {
                'name': 'petId',
                'in': 'path',
                'required': True,
                'description': 'Pet ID',
                'schema': {'type': 'integer'}
            },
            {
                'name': 'limit',
                'in': 'query',
                'required': False,
                'description': 'Limit results',
                'schema': {'type': 'integer'}
            }
        ]
        
        properties, required, docs = self.toolbox._process_parameters(parameters)
        
        assert 'petId' in properties
        assert 'limit' in properties
        assert properties['petId']['type'] == 'integer'
        assert properties['limit']['type'] == 'integer'
        assert 'petId' in required
        assert 'limit' not in required
        assert len(docs) == 2

    def test_extract_parameters_from_schema(self):
        """Test extracting parameters from a schema object."""
        schema = {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': 'Pet name'},
                'age': {'type': 'integer', 'description': 'Pet age'}
            },
            'required': ['name']
        }
        
        parameters = self.toolbox._extract_parameters_from_schema(schema)
        
        assert len(parameters) == 2
        assert parameters[0]['name'] == 'name'
        assert parameters[0]['required'] == True
        assert parameters[1]['name'] == 'age'
        assert parameters[1]['required'] == False

    def test_extract_parameters_from_schema_with_ref(self):
        """Test extracting parameters from a schema with $ref."""
        schema = {'$ref': '#/components/schemas/Pet'}
        
        parameters = self.toolbox._extract_parameters_from_schema(schema)
        
        assert len(parameters) == 2
        name_param = next(p for p in parameters if p['name'] == 'name')
        assert name_param['required'] == True
        tag_param = next(p for p in parameters if p['name'] == 'tag')
        assert tag_param['required'] == False

    def test_process_request_body(self):
        """Test processing of request body parameters."""
        request_body = {
            'required': True,
            'content': {
                'application/json': {
                    'schema': {'$ref': '#/components/schemas/Pet'}
                }
            }
        }
        
        body_params, properties, required, docs = self.toolbox._process_request_body(request_body)
        
        assert 'name' in body_params
        assert 'tag' in body_params
        assert 'name' in properties
        assert 'tag' in properties
        assert 'name' in required
        assert 'tag' not in required
        assert len(docs) == 2

    def test_resolve_reference(self):
        """Test resolving JSON references."""
        ref = '#/components/schemas/Pet'
        resolved = self.toolbox._resolve_reference(ref)
        
        assert resolved['type'] == 'object'
        assert 'name' in resolved['properties']
        assert 'tag' in resolved['properties']
        assert resolved['required'] == ['name']

    def test_resolve_reference_invalid(self):
        """Test resolving invalid JSON references."""
        ref = '#/components/schemas/NonExistent'
        resolved = self.toolbox._resolve_reference(ref)
        
        assert resolved == {}


class TestOpenAPIToolboxIntegration:
    """Integration tests for the complete OpenAPI toolbox."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
        self.json_spec_path = os.path.join(self.fixtures_dir, 'petstore_openapi.json')
    
    def load_fixture(self, filename):
        """Load a test fixture file."""
        filepath = os.path.join(self.fixtures_dir, filename)
        with open(filepath, 'r') as f:
            return json.load(f)

    def test_full_initialization_json(self):
        """Test complete initialization with JSON spec."""
        json_spec = self.load_fixture('petstore_openapi.json')
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(json_spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            toolbox._initialize()
            
            assert toolbox._initialized == True
            assert toolbox.spec == json_spec
            assert toolbox.base_url == 'https://api.petstore.com/v1'

    def test_tools_generation_json(self):
        """Test tool generation from JSON spec."""
        json_spec = self.load_fixture('petstore_openapi.json')
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(json_spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            tools = toolbox.tools()
            
            assert len(tools) == 3  # listPets, createPet, getPet
            tool_names = [tool.name for tool in tools]
            assert 'listPets' in tool_names
            assert 'createPet' in tool_names
            assert 'getPet' in tool_names

    def test_tools_generation_yaml(self):
        """Test tool generation from YAML spec."""
        yaml_spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Pet Store API YAML', 'version': '1.0.0'},
            'servers': [{'url': 'https://api.petstore-yaml.com/v1'}],
            'paths': {
                '/pets': {
                    'get': {
                        'operationId': 'listPetsYaml',
                        'summary': 'List all pets (YAML)',
                        'description': 'Get a list of all pets in the store from YAML spec',
                        'parameters': [
                            {'name': 'limit', 'in': 'query', 'required': False, 'schema': {'type': 'integer'}}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = yaml.dump(yaml_spec)
            mock_response.headers = {'content-type': 'application/yaml'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.yaml')
            tools = toolbox.tools()
            
            assert len(tools) == 1  # listPetsYaml
            assert tools[0].name == 'listPetsYaml'
            assert 'YAML' in tools[0].description

    def test_initialization_error_handling(self):
        """Test error handling during initialization."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            
            with pytest.raises(SpecFetchError):
                toolbox._initialize()
            
            assert toolbox._initialized == False

    def test_reset_functionality(self):
        """Test reset functionality."""
        json_spec = self.load_fixture('petstore_openapi.json')
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(json_spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://example.com/openapi.json')
            toolbox._initialize()
            
            assert toolbox._initialized == True
            assert toolbox.spec is not None
            assert toolbox.base_url is not None
            
            toolbox.reset()
            
            assert toolbox._initialized == False
            assert toolbox.spec is None
            assert toolbox.base_url is None


class TestOpenAPIEndpointToToolMapping:
    """Test suite for verifying OpenAPI endpoints are correctly mapped to LLM Tools."""
    
    def test_basic_endpoint_to_tool_mapping(self):
        """Test that OpenAPI endpoints are correctly converted to LLM tools."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.test.com"}],
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "listUsers",
                        "summary": "List users",
                        "description": "Get all users"
                    }
                },
                "/users/{id}": {
                    "get": {
                        "operationId": "getUser",
                        "summary": "Get user",
                        "description": "Get user by ID",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://api.test.com/openapi.json')
            tools = toolbox.tools()
            
            # Verify correct number of tools
            assert len(tools) == 2
            
            # Verify tool names match operation IDs
            tool_names = [tool.name for tool in tools]
            assert 'listUsers' in tool_names
            assert 'getUser' in tool_names
            
            # Verify tools are proper llm.Tool instances
            for tool in tools:
                assert isinstance(tool, llm.Tool)
                assert hasattr(tool, 'name')
                assert hasattr(tool, 'description')
                assert hasattr(tool, 'implementation')
                assert hasattr(tool, 'input_schema')

    def test_parameters_mapping_to_input_schema(self):
        """Test that OpenAPI parameters are correctly mapped to tool input schemas."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.test.com"}],
            "paths": {
                "/search": {
                    "get": {
                        "operationId": "search",
                        "summary": "Search",
                        "description": "Search with parameters",
                        "parameters": [
                            {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                            {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
                            {"name": "Authorization", "in": "header", "required": True, "schema": {"type": "string"}}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://api.test.com/openapi.json')
            tools = toolbox.tools()
            
            search_tool = tools[0]
            schema = search_tool.input_schema
            
            # Verify schema structure
            assert schema['type'] == 'object'
            assert 'properties' in schema
            assert 'required' in schema
            
            # Verify all parameters are in schema
            properties = schema['properties']
            assert 'q' in properties
            assert 'limit' in properties
            assert 'Authorization' in properties
            
            # Verify parameter types
            assert properties['q']['type'] == 'string'
            assert properties['limit']['type'] == 'integer'
            assert properties['Authorization']['type'] == 'string'
            
            # Verify required parameters
            required = schema['required']
            assert 'q' in required
            assert 'Authorization' in required
            assert 'limit' not in required

    def test_request_body_mapping_to_input_schema(self):
        """Test that OpenAPI request bodies are correctly mapped to tool input schemas."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.test.com"}],
            "paths": {
                "/users": {
                    "post": {
                        "operationId": "createUser",
                        "summary": "Create user",
                        "description": "Create a new user",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["name", "email"],
                                        "properties": {
                                            "name": {"type": "string", "description": "User name"},
                                            "email": {"type": "string", "description": "User email"},
                                            "age": {"type": "integer", "description": "User age"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://api.test.com/openapi.json')
            tools = toolbox.tools()
            
            create_user_tool = tools[0]
            schema = create_user_tool.input_schema
            
            # Verify schema includes request body fields
            properties = schema['properties']
            assert 'name' in properties
            assert 'email' in properties
            assert 'age' in properties
            
            # Verify field types
            assert properties['name']['type'] == 'string'
            assert properties['email']['type'] == 'string'
            assert properties['age']['type'] == 'integer'
            
            # Verify required fields
            required = schema['required']
            assert 'name' in required
            assert 'email' in required
            assert 'age' not in required

    def test_tool_function_execution(self):
        """Test that generated tool functions execute correctly and build proper API requests."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.test.com/v1"}],
            "paths": {
                "/users/{userId}": {
                    "get": {
                        "operationId": "getUser",
                        "summary": "Get user",
                        "description": "Get user by ID",
                        "parameters": [
                            {"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}},
                            {"name": "include", "in": "query", "required": False, "schema": {"type": "string"}}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://api.test.com/openapi.json')
            tools = toolbox.tools()
            
            get_user_tool = tools[0]
            
            # Mock the actual API request
            with patch('requests.request') as mock_request:
                mock_api_response = Mock()
                mock_api_response.status_code = 200
                mock_api_response.json.return_value = {'id': '123', 'name': 'John'}
                mock_api_response.headers = {'content-type': 'application/json'}
                mock_request.return_value = mock_api_response
                
                # Execute the tool
                result = get_user_tool.implementation(userId='123', include='profile')
                
                # Verify the request was built correctly
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                
                assert call_args[1]['method'] == 'GET'
                assert call_args[1]['url'] == 'https://api.test.com/v1/users/123'
                assert call_args[1]['params'] == {'include': 'profile'}
                
                # Verify response format
                assert result['status'] == 200
                assert result['data'] == {'id': '123', 'name': 'John'}

    def test_parameter_reference_handling(self):
        """Test that OpenAPI parameter references are correctly resolved and invalid ones skipped."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.test.com"}],
            "paths": {
                "/search": {
                    "get": {
                        "operationId": "search",
                        "summary": "Search with parameter references",
                        "parameters": [
                            {"$ref": "#/components/parameters/QueryParam"},
                            {"$ref": "#/components/parameters/InvalidRef"},  # This should be skipped
                            {
                                "name": "direct_param",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"}
                            }
                        ]
                    }
                }
            },
            "components": {
                "parameters": {
                    "QueryParam": {
                        "name": "q",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Search query"
                    }
                    # Note: InvalidRef is missing, so reference will fail
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = json.dumps(spec)
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            toolbox = OpenAPIToolbox('https://api.test.com/openapi.json')
            tools = toolbox.tools()
            
            search_tool = tools[0]
            schema = search_tool.input_schema
            properties = schema['properties']
            
            # Should have resolved reference and direct parameter, but not invalid reference
            assert 'q' in properties  # From resolved reference
            assert 'direct_param' in properties  # Direct parameter
            assert len(properties) == 2  # Invalid reference should be skipped
            
            # Verify resolved parameter properties
            assert properties['q']['type'] == 'string'
            assert properties['direct_param']['type'] == 'string'
            
            # Verify required parameter from resolved reference
            required = schema['required']
            assert 'q' in required
            assert 'direct_param' not in required