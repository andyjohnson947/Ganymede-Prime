# Contributing to MT5 Strategy Reversal Bot

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone <your-fork-url>`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes thoroughly
6. Commit with clear messages
7. Push to your fork
8. Create a pull request

## Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure MT5 credentials
python src/gui/account_setup.py
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose
- Comment complex logic

## Adding New Indicators

To add a new indicator:

1. Create a new class in `src/indicators/` that inherits from `BaseIndicator`
2. Implement the `calculate()` method
3. Add the indicator to `indicator_manager.py`
4. Update configuration in `config/config.yaml`

Example:

```python
from .base import BaseIndicator
import pandas as pd

class MyIndicator(BaseIndicator):
    def __init__(self, period: int = 14):
        super().__init__(f"MyIndicator_{period}", {'period': period})
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Your indicator logic here
        df[self.name] = ...
        return df
```

## Adding New Patterns

To add a new pattern detector:

1. Add a new method to `ReversalPatternDetector` in `src/patterns/reversal_patterns.py`
2. Return a list of `PatternResult` objects
3. Update pattern list in `config/config.yaml`

## Testing

- Test with demo accounts only
- Verify all components work independently
- Test integration between components
- Check edge cases (no data, connection failures, etc.)

## Pull Request Guidelines

- Describe what your PR does
- Reference any related issues
- Include tests if applicable
- Update documentation as needed
- Ensure code passes all checks

## Reporting Issues

When reporting issues, please include:

- Python version
- MT5 terminal version
- Error messages and stack traces
- Steps to reproduce
- Expected vs actual behavior

## Questions?

Open an issue with the "question" label or start a discussion.

Thank you for contributing!
