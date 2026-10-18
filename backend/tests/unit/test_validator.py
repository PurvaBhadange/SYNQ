"""
Unit tests for OutputValidator.
Tests code syntax validation, research citation checks, writing structure checks, and acceptance criteria matching.
"""

from core.validator import OutputValidator


def test_validator_rejects_empty():
    val = OutputValidator()
    res = val.validate("code", "")
    assert not res.passed
    assert res.score == 0.0


def test_validator_code_valid_syntax():
    val = OutputValidator()
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = val.validate("code", code)
    assert res.passed
    assert res.checks.get("python_syntax_valid") is True


def test_validator_code_syntax_error():
    val = OutputValidator()
    invalid_code = "def broken(\n    return 42\n"
    res = val.validate("code", invalid_code)
    assert not res.passed
    assert res.checks.get("python_syntax_valid") is False
    assert any("syntax error" in e.lower() for e in res.errors)


def test_validator_research_citations():
    val = OutputValidator()
    good_research = (
        "According to source: https://arxiv.org/abs/2301.00000, graph memory enables "
        "cross-session persistence and reduces prompt overhead across collaborating agents."
    )
    res = val.validate("research", good_research)
    assert res.passed
    assert res.checks.get("has_sources_or_citations") is True


def test_validator_acceptance_criteria():
    val = OutputValidator()
    content = "We have implemented the SQLite database session with async SQLAlchemy connection."
    res = val.validate("general", content, acceptance_criteria="Must provide SQLite database session")
    assert res.passed
    assert res.checks.get("acceptance_criteria_keyword_match") is True


def test_validator_code_crlf_and_markdown_wrapper():
    val = OutputValidator()
    crlf_code = "Here is the implementation:\r\n\r\n```python\r\ndef multiply(x: int, y: int) -> int:\r\n    return x * y\r\n```\r\n\r\nUse this in your module."
    res = val.validate("code", crlf_code)
    assert res.passed
    assert res.checks.get("python_syntax_valid") is True
    assert res.checks.get("has_code_blocks") is True


def test_validator_non_python_code_block():
    val = OutputValidator()
    ts_code = "Here is the component:\n\n```typescript\nimport React from 'react';\nexport const MyComponent: React.FC = () => <div>Hello</div>;\n```"
    res = val.validate("code", ts_code)
    assert res.passed
    assert res.checks.get("has_code_blocks") is True
