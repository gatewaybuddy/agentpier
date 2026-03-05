# Contributing to AgentPier

Thank you for your interest in contributing to AgentPier! This guide will help you get started with contributing to the trust infrastructure for AI agent marketplaces.

## Code of Conduct

This project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainers.

## Development Setup

### Prerequisites

- Python 3.12+
- Git
- AWS CLI (for deployment)
- AWS SAM CLI (for local testing)

### Getting Started

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/agentpier.git
   cd agentpier
   ```

2. **Set up Python Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r tests/requirements-test.txt
   ```

3. **Install Development Dependencies**
   ```bash
   # Core dependencies are minimal (boto3 included in Lambda runtime)
   # Test dependencies include pytest, moto, ruff, bandit, safety
   pip install -r tests/requirements-test.txt
   ```

## Running Tests

### Unit Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_trust.py

# Run with coverage
python -m pytest tests/ --cov=src/ --cov-report=html
```

### Local Development

```bash
# Start local API Gateway
sam local start-api --template infra/template.yaml

# Test individual functions
sam local invoke TrustQueryFunction --event tests/events/trust-query.json
```

## Code Style and Conventions

### Python Style

We follow PEP 8 with these specific conventions:

- **Docstrings**: All modules, classes, and public functions must have docstrings
- **Line length**: 120 characters (extended from PEP 8's 79)
- **Imports**: Absolute imports preferred, group by: stdlib, third-party, local
- **Type hints**: Required for all new functions

Example function structure:
```python
def calculate_trust_score(events: List[Dict], agent_id: str) -> Decimal:
    """Calculate ACE trust score for an agent.
    
    Args:
        events: List of trust events for the agent
        agent_id: Unique agent identifier
        
    Returns:
        Trust score as Decimal (0-100 scale)
        
    Raises:
        ValueError: If events list is empty or agent_id is invalid
    """
```

### API Handler Patterns

All Lambda handlers follow this pattern:

```python
from utils.response import success, error, handler

@handler  # Decorator for error handling and CORS
def my_handler(event, context):
    """Handler description."""
    # Input validation
    body = _parse_body(event)
    
    # Business logic
    result = process_request(body)
    
    # Return response
    return success(result)
```

### Database Patterns

- **Single table design**: All data in one DynamoDB table with PK/SK pattern
- **Consistent naming**: `PK=TYPE#id`, `SK=SUBTYPE#timestamp`
- **TTL fields**: Use `ttl` field for automatic cleanup
- **Pagination**: Use encrypted cursors, not DynamoDB LastEvaluatedKey

### Error Handling

- Use response utilities: `success()`, `error()`, `not_found()`, `unauthorized()`
- Include error codes for programmatic handling
- Log errors with context but avoid sensitive data

## Testing Guidelines

### Test Structure

```python
"""Test module description."""

# Standard test structure
def test_function_name_expected_behavior():
    # Given
    setup_data = create_test_data()
    
    # When
    result = function_under_test(setup_data)
    
    # Then
    assert result == expected_value
    assert side_effect_occurred()
```

### Test Categories

- **Unit tests**: Pure function testing, mocked dependencies
- **Integration tests**: DynamoDB interactions with moto
- **Handler tests**: End-to-end API testing with SAM Local

### Test Data

- Use factories for consistent test data
- Mock external services (Moltbook API, etc.)
- Clean up resources in test teardown

## Pull Request Process

### Before Opening a PR

1. **Check existing issues** — Reference related issues in your PR
2. **Run tests** — Ensure all tests pass locally
3. **Code quality** — Run linting and security scans:
   ```bash
   ruff check src/ tests/
   bandit -r src/
   safety check
   ```
4. **Documentation** — Update API docs if adding/changing endpoints

### PR Requirements

- **Clear description** — What problem does this solve?
- **Issue reference** — Link to related GitHub issue
- **Breaking changes** — Clearly mark any breaking API changes
- **Tests** — Include tests for new functionality
- **Security** — Consider security implications, especially for new endpoints

### PR Template

```markdown
## Description
Brief description of changes

## Related Issues
Fixes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Security Checklist
- [ ] Input validation added
- [ ] Authorization checks included
- [ ] No sensitive data logged
```

### Review Process

1. **Automated checks** — CI must pass (tests, linting, security scans)
2. **Code review** — At least one maintainer approval required
3. **Testing** — Reviewer tests functionality in staging environment
4. **Documentation** — API docs updated if needed

## Issue Labels and Priorities

### Issue Types

- `bug` — Something isn't working
- `feature` — New functionality
- `enhancement` — Improve existing functionality
- `documentation` — Documentation improvements
- `security` — Security-related issues
- `performance` — Performance improvements

### Priority Levels

- `priority-critical` — Security vulnerabilities, data loss, service down
- `priority-high` — Major functionality broken, significant user impact
- `priority-medium` — Feature requests, moderate bugs
- `priority-low` — Nice-to-have improvements, minor issues

### Special Labels

- `good-first-issue` — Good for new contributors
- `help-wanted` — Community contributions welcome
- `breaking-change` — Will require version bump
- `needs-design` — Requires design discussion before implementation

## Architecture Guidelines

### Design Principles

1. **Serverless-first** — Use Lambda, API Gateway, DynamoDB
2. **Single responsibility** — One handler per endpoint
3. **Stateless** — No persistent connections or shared state
4. **Fail fast** — Validate inputs early, return meaningful errors
5. **Audit everything** — Log security-relevant events

### Adding New Endpoints

1. **Handler function** in `src/handlers/`
2. **SAM template** entry in `infra/template.yaml`
3. **Tests** in `tests/test_*.py`
4. **Documentation** in API reference
5. **Rate limiting** configuration
6. **Authentication** requirements

### Database Schema

Follow single-table design patterns:

```python
# Agent record
PK="AGENT#{agent_id}", SK="PROFILE"

# Trust events
PK="AGENT#{agent_id}", SK="EVENT#{timestamp}"

# Marketplace records
PK="MARKETPLACE#{id}", SK="META"
```

## Security Guidelines

### Input Validation

- Validate all user inputs
- Use allowlists for enum values
- Sanitize strings to prevent injection
- Check array/object sizes to prevent DoS

### Authentication

- API key required for most endpoints
- Rate limiting per IP and per key
- Log authentication failures
- Use secure session management

### Data Protection

- No sensitive data in logs
- Encrypt data at rest (DynamoDB)
- Use HTTPS for all communications
- Follow least privilege for IAM roles

## Getting Help

### Communication Channels

- **GitHub Issues** — Bug reports and feature requests
- **GitHub Discussions** — General questions and ideas
- **Security Issues** — Email maintainers directly for security vulnerabilities

### Documentation

- **API Reference** — [docs/api-reference.md](docs/api-reference.md)
- **Architecture** — [docs/architecture.md](docs/architecture.md)
- **Deployment** — [docs/deployment.md](docs/deployment.md)

### Maintainers

Current maintainers:
- [@gatewaybuddy](https://github.com/gatewaybuddy) — Lead maintainer

## License

By contributing to AgentPier, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).