"""Tests for agent database tools."""

import unittest
from unittest.mock import MagicMock, patch
from src.utils.agent_tools import AgentDatabaseTools
from src.database.database_interface import DatabaseInterface
from src.ontology.ontology_manager import OntologyManager

class TestAgentDatabaseTools(unittest.TestCase):
    """Test cases for AgentDatabaseTools."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock interfaces with required methods
        self.db_interface = MagicMock()
        self.db_interface.get_entity = MagicMock()
        self.db_interface.get_entities = MagicMock()
        self.db_interface.add_entity = MagicMock()
        self.db_interface.update_entity = MagicMock()
        
        self.ontology_manager = MagicMock()
        self.ontology_manager.get_schema = MagicMock()
        
        # Set up test data
        self.test_entity = {"id": "test1", "name": "Test Entity"}
        self.test_schema = {"type": "object", "properties": {}}
        
        # Configure mock returns
        self.db_interface.get_entity.return_value = self.test_entity
        self.db_interface.get_entities.return_value = [self.test_entity]
        self.ontology_manager.get_schema.return_value = self.test_schema
        self.ontology_manager.schemas = {"test": self.test_schema}
    
    def test_init_with_valid_role(self):
        """Test initialization with valid roles."""
        analyzer = AgentDatabaseTools(self.db_interface, self.ontology_manager, "analyzer")
        self.assertEqual(analyzer.role, "analyzer")
        
        curator = AgentDatabaseTools(self.db_interface, self.ontology_manager, "curator")
        self.assertEqual(curator.role, "curator")
    
    def test_init_with_invalid_role(self):
        """Test initialization with invalid role."""
        with self.assertRaises(ValueError):
            AgentDatabaseTools(self.db_interface, self.ontology_manager, "invalid_role")
    
    def test_get_tool_schemas(self):
        """Test getting tool schemas for different roles."""
        analyzer = AgentDatabaseTools(self.db_interface, self.ontology_manager, "analyzer")
        curator = AgentDatabaseTools(self.db_interface, self.ontology_manager, "curator")
        
        analyzer_schemas = analyzer.get_tool_schemas()
        curator_schemas = curator.get_tool_schemas()
        
        # Analyzer should have all methods
        self.assertEqual(len(analyzer_schemas), 5)  # All read and write methods
        
        # Curator should only have read methods
        self.assertEqual(len(curator_schemas), 3)  # Only read methods
        
        # Verify schema structure
        for schema in analyzer_schemas:
            self.assertIn("name", schema)
            self.assertIn("description", schema)
            self.assertIn("parameters", schema)
    
    def test_read_permissions(self):
        """Test read permissions for different roles."""
        curator = AgentDatabaseTools(self.db_interface, self.ontology_manager, "curator")
        
        # Should succeed
        curator.get_entity("test", "1")
        curator.get_entities("test")
        curator.get_schema("test")
        
        # Should fail
        with self.assertRaises(PermissionError):
            curator.add_entity("test", "1", {})
        with self.assertRaises(PermissionError):
            curator.update_entity("test", "1", {})
    
    def test_write_permissions(self):
        """Test write permissions for different roles."""
        analyzer = AgentDatabaseTools(self.db_interface, self.ontology_manager, "analyzer")
        
        # Should succeed (both read and write)
        analyzer.get_entity("test", "1")
        analyzer.add_entity("test", "1", {})
        analyzer.update_entity("test", "1", {})
    
    def test_get_entity(self):
        """Test getting an entity."""
        tools = AgentDatabaseTools(self.db_interface, self.ontology_manager, "curator")
        result = tools.get_entity("test", "1")
        
        self.db_interface.get_entity.assert_called_once_with("test", "1")
        self.assertEqual(result, self.test_entity)
    
    def test_get_entities(self):
        """Test getting all entities of a type."""
        tools = AgentDatabaseTools(self.db_interface, self.ontology_manager, "curator")
        result = tools.get_entities("test")
        
        self.db_interface.get_entities.assert_called_once_with("test")
        self.assertEqual(result, [self.test_entity])
    
    def test_get_schema(self):
        """Test getting schema information."""
        tools = AgentDatabaseTools(self.db_interface, self.ontology_manager, "curator")
        
        # Get specific schema
        result = tools.get_schema("test")
        self.ontology_manager.get_schema.assert_called_once_with("test")
        self.assertEqual(result, self.test_schema)
        
        # Get all schemas
        result = tools.get_schema()
        self.assertEqual(result, self.ontology_manager.schemas)
    
    def test_add_entity(self):
        """Test adding an entity."""
        tools = AgentDatabaseTools(self.db_interface, self.ontology_manager, "analyzer")
        tools.add_entity("test", "1", self.test_entity)
        
        self.db_interface.add_entity.assert_called_once_with(
            "test", "1", self.test_entity
        )
    
    def test_update_entity(self):
        """Test updating an entity."""
        tools = AgentDatabaseTools(self.db_interface, self.ontology_manager, "analyzer")
        tools.update_entity("test", "1", self.test_entity)
        
        self.db_interface.update_entity.assert_called_once_with(
            "test", "1", self.test_entity
        ) 