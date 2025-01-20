import unittest
import uuid
from typing import Dict, List, Any, Optional, Union
from src.database.database_interface import DatabaseInterface
from src.utils.exceptions import DatabaseError
import json

class MockDatabase(DatabaseInterface):
    """Mock implementation of the flexible database interface for testing."""
    
    def __init__(self):
        self.collections = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]
        self.schemas = {}  # type: Dict[str, Dict[str, Any]]
        self.links = []  # type: List[Dict[str, Any]]

    def create_collection(self, collection_name: str, schema: Optional[Dict[str, Any]] = None) -> None:
        self.collections[collection_name] = {}
        if schema:
            self.schemas[collection_name] = schema

    def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        return self.schemas.get(collection_name, {})

    def update_collection_schema(self, collection_name: str, schema: Dict[str, Any]) -> None:
        self.schemas[collection_name] = schema

    def insert(self, collection_name: str, data: Dict[str, Any], entity_id: Optional[str] = None) -> str:
        if collection_name not in self.collections:
            raise DatabaseError(f"Collection {collection_name} does not exist")
            
        if entity_id is None:
            entity_id = str(uuid.uuid4())
            
        self.collections[collection_name][entity_id] = data
        return entity_id

    def find_by_id(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        return self.collections.get(collection_name, {}).get(entity_id, {})

    def find(self, collection_name: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for entity in self.collections.get(collection_name, {}).values():
            matches = True
            for key, value in query.items():
                if key not in entity or entity[key] != value:
                    matches = False
                    break
            if matches:
                results.append(entity)
        return results

    def update(self, collection_name: str, entity_id: str, data: Dict[str, Any], 
               upsert: bool = False) -> None:
        if collection_name not in self.collections:
            raise DatabaseError(f"Collection {collection_name} does not exist")
            
        if entity_id not in self.collections[collection_name] and not upsert:
            raise DatabaseError(f"Entity {entity_id} not found")
            
        if entity_id not in self.collections[collection_name]:
            self.collections[collection_name][entity_id] = {}
            
        self.collections[collection_name][entity_id].update(data)

    def delete(self, collection_name: str, entity_id: str) -> None:
        if collection_name in self.collections and entity_id in self.collections[collection_name]:
            del self.collections[collection_name][entity_id]

    def create_link(self, from_collection: str, from_id: str, 
                   to_collection: str, to_id: str,
                   link_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        link_id = str(uuid.uuid4())
        link = {
            "id": link_id,
            "from_collection": from_collection,
            "from_id": from_id,
            "to_collection": to_collection,
            "to_id": to_id,
            "link_type": link_type,
            "metadata": metadata or {}
        }
        self.links.append(link)
        return link_id

    def find_links(self, collection_name: str, entity_id: str, 
                  link_type: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for link in self.links:
            if ((link["from_collection"] == collection_name and link["from_id"] == entity_id) or
                (link["to_collection"] == collection_name and link["to_id"] == entity_id)):
                if link_type is None or link["link_type"] == link_type:
                    results.append(link)
        return results

    def execute_query(self, query: Union[str, Dict[str, Any]], 
                     params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError("Mock database does not support native queries")

    def begin_transaction(self) -> None:
        pass  # No-op in mock

    def commit_transaction(self) -> None:
        pass  # No-op in mock

    def rollback_transaction(self) -> None:
        pass  # No-op in mock

    def close(self) -> None:
        self.collections.clear()
        self.schemas.clear()
        self.links.clear()


class TestDatabaseInterface(unittest.TestCase):
    def setUp(self):
        self.db = MockDatabase()
        
        # Create test collections
        self.db.create_collection("users", {
            "required_fields": ["name"]
        })
        self.db.create_collection("documents")
        
        # Create test user
        self.user_id = self.db.insert("users", {"name": "test user"})

    def test_create_and_get_schema(self):
        schema = {"required_fields": ["title", "content"]}
        self.db.create_collection("articles", schema)
        retrieved_schema = self.db.get_collection_schema("articles")
        self.assertEqual(retrieved_schema, schema)

    def test_insert_and_find_by_id(self):
        doc_id = self.db.insert("documents", {"title": "Test Doc"})
        doc = self.db.find_by_id("documents", doc_id)
        self.assertEqual(doc["title"], "Test Doc")

    def test_find_with_query(self):
        self.db.insert("documents", {"type": "note", "status": "active"})
        self.db.insert("documents", {"type": "note", "status": "archived"})
        
        active_docs = self.db.find("documents", {"status": "active"})
        self.assertEqual(len(active_docs), 1)
        self.assertEqual(active_docs[0]["status"], "active")

    def test_update(self):
        doc_id = self.db.insert("documents", {"title": "Old Title"})
        self.db.update("documents", doc_id, {"title": "New Title"})
        doc = self.db.find_by_id("documents", doc_id)
        self.assertEqual(doc["title"], "New Title")

    def test_delete(self):
        doc_id = self.db.insert("documents", {"title": "To Delete"})
        self.db.delete("documents", doc_id)
        doc = self.db.find_by_id("documents", doc_id)
        self.assertEqual(doc, {})

    def test_create_and_find_links(self):
        doc_id = self.db.insert("documents", {"title": "Test Doc"})
        
        link_id = self.db.create_link(
            "users", self.user_id,
            "documents", doc_id,
            "created",
            {"timestamp": "2024-01-20"}
        )
        
        links = self.db.find_links("users", self.user_id, "created")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["link_type"], "created")
        self.assertEqual(links[0]["from_id"], self.user_id)
        self.assertEqual(links[0]["to_id"], doc_id)


if __name__ == '__main__':
    unittest.main()
