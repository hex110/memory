# Testing Strategy

This directory contains unit tests for the Memory project. The tests are designed to be:
- Independent: Each test can run in isolation
- Maintainable: Tests are structured to minimize brittleness
- Fast: No external dependencies required
- Comprehensive: Testing both happy paths and edge cases

## Test Structure

### Database Tests (`test_database.py`)
- Uses `MockDatabase` for testing database operations
- In-memory implementation of `DatabaseInterface`
- No external database required
- Tests CRUD operations and relationships

### Ontology Tests (`test_ontology.py`)
- Tests ontology management functionality
- Validates schema structure rather than exact content
- Maintains state consistency between tests
- Tests concept and relationship operations

## Running Tests

Run all tests:
```bash
python -m unittest discover src/tests
```

Run specific test file:
```bash
python -m unittest src/tests/test_database.py
python -m unittest src/tests/test_ontology.py
```

## Best Practices

1. **Mock External Dependencies**
   - Use mock implementations for external services
   - Keep tests fast and reliable
   - Avoid network/database dependencies

2. **Test Structure**
   - Each test should have clear arrange/act/assert phases
   - Use descriptive test names
   - Include docstrings explaining test purpose

3. **State Management**
   - Clean up after tests
   - Don't rely on test execution order
   - Restore modified state in tearDown

4. **Assertions**
   - Test behavior, not implementation
   - Use appropriate assertions
   - Include meaningful error messages

5. **Maintenance**
   - Keep tests simple and focused
   - Update tests when interfaces change
   - Document test requirements and assumptions 