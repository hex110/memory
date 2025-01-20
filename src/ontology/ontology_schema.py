ontology_schema = {
    "concepts": {
        "user": {"description": "A person using the system"},
        "conversation": {"description": "A text-based interaction"},
        "relationship": {"description": "A link between two things"},
        "tag": {"description": "A label to categorize data"}
    },
    "relationships": {
        "related_to": {
            "description": "Represents some relationship between two items",
            "source_type": "user",
            "target_type": "conversation"
        },
        "tagged_with": {
            "description": "Marks which items are tagged with which labels",
            "source_type": "conversation",
            "target_type": "tag"
        }
    },
    "data_types": {
        "uuid": {"description": "Unique id for all database objects"},
        "text": {"description": "Text value"},
        "json": {"description": "JSON object"},
        "timestamp": {"description": "Date and time value"},
    }
}
