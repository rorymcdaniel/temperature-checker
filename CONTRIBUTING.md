# Contributing

Thanks for your interest in improving Temperature Checker! 

## How to Contribute

**Just open a Pull Request!** Whether it's a bug fix, improvement, or new feature - PRs are welcome.

## Requirements

1. **Include tests** for your changes
   - New features need tests
   - Bug fixes should include a test that reproduces the issue
   - Run `poetry run pytest` to make sure everything passes

2. **Maintain test coverage**
   - Keep coverage above 94%
   - Check with `poetry run pytest --cov-report=term-missing`

3. **Follow existing patterns**
   - Look at the existing code style
   - Use similar naming and structure

## Quick Setup

```bash
# Fork the repo, then:
git clone https://github.com/YOUR_USERNAME/temperature-checker.git
cd temperature-checker
poetry install
poetry run pytest  # Make sure tests pass
```

## That's it!

The CI will automatically test your changes against Python 3.8-3.11. If tests pass and coverage is good, your PR will be ready for review.