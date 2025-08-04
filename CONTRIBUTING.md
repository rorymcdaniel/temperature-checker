# Contributing to Temperature Checker

Thank you for your interest in contributing to Temperature Checker! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/temperature-checker.git
   cd temperature-checker
   ```
3. **Install dependencies** using Poetry:
   ```bash
   poetry install
   ```
4. **Create a feature branch** from main:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Guidelines

### Code Requirements

- **Python Compatibility**: Code must work with Python 3.8, 3.9, 3.10, and 3.11
- **Code Style**: Follow existing code patterns and conventions
- **Type Hints**: Use type hints where appropriate
- **Documentation**: Add docstrings for new functions and classes

### Testing Requirements

**All contributions must include appropriate test coverage:**

- **New features**: Write unit tests and integration tests as needed
- **Bug fixes**: Include tests that reproduce the bug and verify the fix
- **Minimum coverage**: Maintain the current 94%+ test coverage
- **Test types**:
  - Unit tests for individual functions/methods
  - Integration tests for end-to-end workflows
  - Mock external dependencies (APIs, file system, etc.)

### Running Tests

Before submitting your PR, ensure all tests pass:

```bash
# Run all tests with coverage
poetry run pytest

# Run tests for specific file
poetry run pytest test_temp_checker.py

# Run with verbose output
poetry run pytest -v

# Generate coverage report
poetry run pytest --cov-report=html
```

## Submission Process

### Pull Request Guidelines

1. **Create a descriptive PR title**:
   - ✅ Good: "Add heating mode threshold validation"
   - ❌ Bad: "Fix bug"

2. **Write a clear PR description**:
   - Explain what the change does
   - Reference any related issues
   - Include testing information

3. **Ensure CI passes**:
   - All tests must pass on Python 3.8, 3.9, 3.10, 3.11
   - Coverage must remain above 94%
   - No linting errors

4. **Keep PRs focused**:
   - One feature or fix per PR
   - Avoid mixing unrelated changes

### Example PR Description Template

```markdown
## Summary
Brief description of what this PR does.

## Changes
- List of specific changes made
- Another change

## Testing
- [ ] Added unit tests for new functionality
- [ ] Added integration tests if needed
- [ ] All existing tests pass
- [ ] Coverage remains above 94%

## Related Issues
Fixes #123
```

## Development Setup

### Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Configure your local settings (optional for development):
   - Add your ZIP code for testing
   - Add Telegram credentials if testing notifications

### Database Testing

Tests use in-memory SQLite databases and don't require external setup.

## Code Areas

### Main Components

- **`temp_checker_refactored.py`**: Core application logic
- **`set_window_state.py`**: Utility script for manual state management
- **`database_schema.sql`**: Database schema definition

### Test Structure

- **`test_temp_checker.py`**: Unit tests for core functionality
- **`test_integration.py`**: End-to-end integration tests
- **`test_utility.py`**: Tests for utility script

## Common Contribution Areas

### Easy First Contributions

- **Documentation improvements**: Fix typos, clarify instructions
- **Error handling**: Add better error messages or edge case handling
- **Configuration validation**: Validate environment variables
- **Logging improvements**: Add more informative log messages

### Intermediate Contributions

- **New notification channels**: Add support for other messaging services
- **Weather API alternatives**: Add support for additional weather services
- **Enhanced scheduling**: Improve timing and scheduling logic
- **Performance optimizations**: Database queries, API calls, etc.

### Advanced Contributions

- **New modes**: Add seasonal or custom temperature modes
- **Web interface**: Add a simple web UI for configuration
- **Historical analysis**: Add temperature trend analysis
- **Multi-location support**: Support monitoring multiple locations

## Getting Help

- **Questions**: Open a GitHub issue with the "question" label
- **Bugs**: Open a GitHub issue with the "bug" label
- **Feature requests**: Open a GitHub issue with the "enhancement" label

## Code of Conduct

- Be respectful and constructive in all interactions
- Follow the existing code style and patterns
- Write clear commit messages and PR descriptions
- Be patient during the review process

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Temperature Checker! 🌡️