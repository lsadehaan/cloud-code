# Contributing to Cloud Code

Thanks for your interest in contributing to Cloud Code! This project turns GitHub Issues into Pull Requests using autonomous AI agents.

## 🚧 Project Status

Cloud Code is in early development (MVP phase). We welcome contributions, but please note that core APIs may change.

## Getting Started

1. **Fork the repository**
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/cloud-code.git
   cd cloud-code
   ```

3. **Set up development environment:**
   ```bash
   cp .env.example .env
   docker-compose up -d postgres redis vault
   cd src && python -m cloud_code.main
   ```

4. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## What to Contribute

### Good First Issues

Look for issues labeled `good first issue` - these are great for newcomers.

### Areas Needing Help

- **New CLI integrations** - Add support for more coding CLIs
- **Documentation** - Improve setup guides, add examples
- **Testing** - Add unit and integration tests
- **Bug fixes** - Check open issues

### Current Priorities

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the current roadmap.

## Development Workflow

### Code Style

- Python 3.12+ with type hints
- Use `async/await` for I/O operations
- Follow existing patterns in the codebase

### Running Tests

```bash
pytest tests/ -v
```

### Type Checking

```bash
mypy src/cloud_code
```

### Submitting Changes

1. Ensure tests pass
2. Update documentation if needed
3. Commit with a clear message:
   ```bash
   git commit -m "feat: add support for X CLI"
   ```
4. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
5. Open a Pull Request

### Commit Message Format

We use conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code change that neither fixes a bug nor adds a feature
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

## Adding a New Coding CLI

1. Create Dockerfile in `docker/agents/{cli-name}/`
2. Add CLI class in `agent_control_plane/cli_runner.py`
3. Add config in `core/container_manager.py`
4. Add Vault credential mapping in `core/vault.py`
5. Update documentation

See existing CLI implementations for examples.

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
