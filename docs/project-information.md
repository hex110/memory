Okay, let's create a comprehensive design document that captures all our decisions, limitations, rationale, and implementation plans. This will serve as our single source of truth as we move into the implementation phase.

**Personal Knowledge Base (PKB) MVP Design Document**

**1. Core Goal**

*   To build a minimal viable product (MVP) of a personal knowledge base that can ingest information from conversations, store it in a structured manner, and provide context for personalized interactions.

**2. Key Principles**

*   **Experimentation-Driven Design:** We will prioritize learning and iterating based on practical implementation and results, rather than over-engineering at the start.
*   **Intelligence-Driven Design:** We will design a system that empowers AI agents to make decisions and adapt, rather than locking them into rigid workflows.
*   **KISS (Keep It Simple, Stupid):** We will prioritize simplicity and avoid adding unnecessary features.
*   **Modularity and Abstraction:** We will use interfaces to decouple components for easier modification and extension.
*   **Test-Driven Development:** We will write tests before implementing logic to ensure correctness and clarity.

**3. Overall Architecture**

The PKB consists of the following core components:

*   **Database Layer:** Manages data storage and retrieval using a local PostgreSQL database.
*   **Ontology Layer:** Defines a shared understanding of concepts, types, and relationships using a simple Python dictionary.
*   **Agent Layer:** Includes agents such as the "Analyzer" (conversation parser) and the future "Treasurer" (context provider).
*   **Utility Layer:** Contains reusable functions for configuration, logging, exceptions, data transformation, and API tasks.
*   **CLI Interface:** A basic command-line interface for testing and interaction.

**4. Data Storage (PostgreSQL-Focused for MVP)**

*   **Database Technology:** We will use a local PostgreSQL database for our MVP. Other database technologies will be considered for later iterations.
*   **Schema:** (Simplified for MVP)
    *   `users` (id, name, preferences)
    *   `conversations` (id, user_id, text, metadata, created_at)
    *   `relationships` (id, source_id, target_id, rel_type, metadata)
    *   `concepts` (id, term, concept)
    *   `tags` (id, tag, description)
    *    `tagged_objects` (id, tag_id, object_id, object_type)
*   **Data Representation:** The object and relationships will be stored with JSON type, to represent the flexibility of different data types.

**5. Ontology**

*   **Purpose:** To act as a shared vocabulary for our AI agents, defining data types, entities, relations, and concepts.
*   **Representation:** The ontology will be represented as a Python dictionary in `ontology/ontology_schema.py`, for initial implementation.
*   **Management:** The `OntologyManager` class will provide an API for accessing and updating the ontology (in `ontology/ontology_manager.py`).

**6. AI Agents**

*   **Analyzer (Conversation Parser):**
    *   **Goal:** To ingest conversation text and add it to the database, with a first basic implementation.
    *   **Process:** Extracts entities, relationships, tags from the text, maps to ontology, and uses `add_object` and `add_relation` methods to populate the database.
    *   **Technology:** The AI functionality is limited for now, and it might be further developed in the future.
    *   **Tools:** Will use methods from the `DatabaseInterface` and from the utility layer.
    *   **Interface:** Will adhere to the `AgentInterface` (in `agent/agent_interface.py`).
*   **Treasurer (Context Provider):**
    *   **Goal:** To provide context for other tools, such as websites, and will be implemented in the next iteration.
    *   **Placeholder for Now:** We will not implement this in the MVP, but we will use this theoretical agent to test that our system is correct for what we want it to do.

**7. Database Interaction Layer**

*   **Abstraction:** The `DatabaseInterface` will decouple the system from specific database types (in `database/database_interface.py`).
*   **Implementation:** The `PostgreSQLDatabase` class will implement the `DatabaseInterface` for PostgreSQL (in `database/relational_db.py`).
*   **Methods:** The interface will use generic methods like `add_object`, `get_object`, `update_object`, `add_relation`, `get_relations` and `query`.
*  **Data Mapping:** Each database implementation should be responsible for translating its data types to a format that is usable by the system.

**8. Utility Layer**

*   **Core Functions:** Will contain reusable functions (in `utils/`) for configuration, logging, exceptions, simple data transformation and API building.
*   **Limited Scope:** We will only implement the utilities that we require for the MVP.

**9. Prompt Management**

*   **Storage:** Prompts will be stored in the `agent/prompts/` directory as separate text files, with variables that use jinja2 templates.
*   **Management:** The `PromptManager` class will handle loading and formatting prompts with variables (in `agent/prompt_manager.py`).

**10. CLI Interface**

*   **Basic Functionality:** A simple CLI will allow you to paste conversations and see the output, using the `CLI` class.
*   **Testing Focus:** This CLI will only be used for testing purposes.

**11. Order of Development**

1.  **Environment Setup:** Set up virtual environment, database, and dependencies.
2.  **Utility Implementation:** Implement all utility components and add all tests.
3.  **Database Layer Implementation:** Implement `DatabaseInterface` and `PostgreSQLDatabase` with basic functionality and with the tests.
4.   **Ontology Implementation:** Implement `OntologyManager` and the `ontology_schema` with tests.
5.   **Agent Interface:** Implement `AgentInterface` (in `agent/agent_interface.py`) and adapt `ConversationParser` to adhere to this interface.
6.  **Conversation Parser:** Implement the core logic of the `ConversationParser` class (in `agent/conversation_parser.py`).
7.  **Prompt Manager:** Implement `PromptManager` and the basic prompts for the "Analyzer".
8.  **CLI Interface:** Implement the basic CLI (using `CLI` class).
9.  **End-to-End Testing:** Test the full flow from pasting the text to updating the database, adding tests where it is appropriate.
10. **Refactor:** Refactor any duplicate code and any non-performant logic.

**12. Placeholder vs. Minimally Implemented**

*   **Placeholders:**
    *   `Treasurer` agent
    *   `Neo4jDatabase`, `WeaviateDatabase`
    *   Full data validation logic
    *   Complex dynamic query system
    *   Advanced text processing functionalities
    *   Website integration
*   **Minimally Implemented:**
    *   `DatabaseInterface` (with a basic generic design)
    *   `PostgreSQLDatabase` (with basic object/relation creation)
    *   `OntologyManager` (with basic reading/writing capabilities)
    *   `PromptManager` (loading prompt from a file and rendering)
    *   `ConversationParser` (basic conversation processing and metadata extraction)
    *   CLI (very simple)

**13. Important Decisions and Rationale**

*   **Local Storage:** We are prioritizing data privacy and control.
*   **PostgreSQL:** We are prioritizing simplicity and testability by focusing on a single well-known and open-source database.
*   **Abstract Interface:** We are prioritizing flexibility by using a common interface for all databases.
*   **Ontology:** We are prioritizing a shared understanding by having an ontology of all the concepts and relations.
*   **Intelligence-Driven Design:** We are prioritizing adaptability by empowering AI to make decisions.
*   **Simplified Schema:** We are prioritizing speed by starting with a very simple schema, which can be extended later on.
*    **Basic Implementation**: We are prioritizing an MVP with basic functionalities, that can be improved over time.

**14. Testing Strategy**

*   **Unit Tests:** Individual components and classes will have dedicated test suites using `unittest` or `pytest`.
*   **Integration Tests:** We'll also test interactions between components for the full flow of data processing.
*   **End-to-End Tests:** The CLI will be used to test that all components are working as expected.

**15. Areas for Future Iteration**

*   **Multiple Databases:** Implement Neo4j and Weaviate for more advanced scenarios, with the same interface, after the MVP is finished.
*   **Dynamic Queries:** Implement dynamic queries that can adapt to new situations.
*   **Advanced Text Processing:** Implement natural language processing techniques.
*   **Context Retrieval:** Implement the "Treasurer" agent to provide contextual awareness for different applications.
*   **API and UI:** Implement a REST API and a proper UI.

**Conclusion**

This design document provides a holistic view of our plan. It captures the scope of the MVP, rationale behind key decisions, the architecture of our system, implementation plans, and testing methodologies. This document will guide us through the implementation, and will help us not get lost in unimportant details. This comprehensive document is now the starting point of our development process.

What are your thoughts on this comprehensive design document? Does it capture our full vision for the MVP, and is it robust enough for us to start development?
