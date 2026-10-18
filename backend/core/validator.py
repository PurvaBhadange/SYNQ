"""
Output Validator for SYNQ Task Executions.

Validates provider responses based on task type and acceptance criteria.
Ensures outputs are non-trivial, well-structured, syntactically valid for code,
and meet project safety and quality gates before committing to project memory.
"""

import ast
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    passed: bool
    score: float  # 0.0 to 1.0
    summary: str
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": round(self.score, 2),
            "summary": self.summary,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class OutputValidator:
    """
    Validates task outputs across different task types.
    """

    def validate(
        self,
        task_type: str,
        content: str,
        structured_output: Optional[Dict[str, Any]] = None,
        acceptance_criteria: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate task output according to task type and acceptance criteria.
        """
        if not content or not content.strip():
            return ValidationResult(
                passed=False,
                score=0.0,
                summary="Output is empty or whitespace only.",
                checks={"non_empty": False},
                errors=["Empty response received from provider."],
            )

        checks: Dict[str, bool] = {"non_empty": True}
        errors: List[str] = []
        warnings: List[str] = []

        # Minimum length check (at least 20 chars for any valid work)
        if len(content.strip()) < 20:
            checks["sufficient_length"] = False
            errors.append(f"Output is too short ({len(content.strip())} characters).")
        else:
            checks["sufficient_length"] = True

        # Dispatch type-specific validation
        if task_type == "code":
            self._validate_code(content, checks, errors, warnings)
        elif task_type == "research":
            self._validate_research(content, checks, errors, warnings)
        elif task_type == "write":
            self._validate_write(content, checks, errors, warnings)
        elif task_type == "analyze":
            self._validate_analyze(content, checks, errors, warnings)
        elif task_type == "plan":
            self._validate_plan(content, structured_output, checks, errors, warnings)

        # Acceptance criteria check if provided
        if acceptance_criteria:
            self._validate_acceptance_criteria(content, acceptance_criteria, checks, warnings)

        passed = len(errors) == 0
        total_checks = len(checks)
        passed_checks = sum(1 for v in checks.values() if v)
        score = (passed_checks / total_checks) if total_checks > 0 else 1.0

        if not passed:
            summary = f"Validation failed: {', '.join(errors)}"
        elif warnings:
            summary = f"Validation passed with warnings: {', '.join(warnings)}"
        else:
            summary = "Validation passed successfully."

        return ValidationResult(
            passed=passed,
            score=score,
            summary=summary,
            checks=checks,
            errors=errors,
            warnings=warnings,
        )

    def _validate_code(
        self,
        content: str,
        checks: Dict[str, bool],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        # Check if contains any fenced code block (with optional language tag and CRLF/LF)
        all_blocks = re.findall(r"```([a-zA-Z0-9_+-]*)\r?\n(.*?)```", content, re.DOTALL)
        if all_blocks:
            checks["has_code_blocks"] = True
            py_blocks = [code for lang, code in all_blocks if lang.lower() in ("python", "py")]
            generic_blocks = [code for lang, code in all_blocks if not lang.strip()]
            other_blocks = [code for lang, code in all_blocks if lang.strip() and lang.lower() not in ("python", "py")]

            if py_blocks:
                code_to_check = "\n\n".join(py_blocks)
                is_python = True
            elif generic_blocks and not other_blocks:
                code_to_check = "\n\n".join(generic_blocks)
                is_python = ("def " in code_to_check or "import " in code_to_check or "class " in code_to_check)
            else:
                code_to_check = ""
                is_python = False
        else:
            code_to_check = content
            checks["has_code_blocks"] = False
            warnings.append("No explicit markdown code blocks found.")
            is_python = ("def " in code_to_check or "class " in code_to_check)

        # If python code detected or claimed, try syntax parsing
        if is_python and code_to_check.strip():
            try:
                ast.parse(code_to_check)
                checks["python_syntax_valid"] = True
            except SyntaxError as err:
                checks["python_syntax_valid"] = False
                errors.append(f"Python syntax error at line {err.lineno}: {err.msg}")
        else:
            checks["python_syntax_valid"] = True

    def _validate_research(
        self,
        content: str,
        checks: Dict[str, bool],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        # Research outputs should have citations, links, or structured references
        has_citations = any(
            marker in content.lower()
            for marker in ["http://", "https://", "source:", "reference:", "citation:", "according to"]
        )
        checks["has_sources_or_citations"] = has_citations
        if not has_citations:
            warnings.append("Research output does not include explicit source citations or URLs.")

        # Check for substantive length (at least 100 characters for research)
        if len(content.strip()) < 100:
            checks["substantive_depth"] = False
            errors.append("Research output lacks substantive detail (under 100 characters).")
        else:
            checks["substantive_depth"] = True

    def _validate_write(
        self,
        content: str,
        checks: Dict[str, bool],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        # Writing should have structured sections or paragraphs
        has_headings = bool(re.search(r"^#{1,4}\s+.+", content, re.MULTILINE))
        checks["has_headings"] = has_headings
        if not has_headings and len(content) > 300:
            warnings.append("Document lacks markdown headings for readability.")

        word_count = len(content.split())
        checks["adequate_word_count"] = word_count >= 15
        if word_count < 15:
            errors.append(f"Written text is too short ({word_count} words).")

    def _validate_analyze(
        self,
        content: str,
        checks: Dict[str, bool],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        # Analysis should contain structured bullet points or breakdown
        has_lists = bool(re.search(r"^\s*[-*•\d\.]+\s+.+", content, re.MULTILINE))
        checks["structured_points"] = has_lists
        if not has_lists:
            warnings.append("Analysis lacks bulleted or numbered breakdown points.")

    def _validate_plan(
        self,
        content: str,
        structured_output: Optional[Dict[str, Any]],
        checks: Dict[str, bool],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        if structured_output and "tasks" in structured_output:
            checks["structured_tasks_present"] = True
            tasks = structured_output.get("tasks", [])
            if not isinstance(tasks, list) or len(tasks) == 0:
                checks["valid_task_list"] = False
                errors.append("Planner structured output has empty or invalid 'tasks' list.")
            else:
                checks["valid_task_list"] = True
        else:
            # Fallback check on content
            has_tasks = "task" in content.lower() or "step" in content.lower()
            checks["mentions_tasks"] = has_tasks
            if not has_tasks:
                warnings.append("Plan output does not clearly list subtasks or steps.")

    def _validate_acceptance_criteria(
        self,
        content: str,
        acceptance_criteria: str,
        checks: Dict[str, bool],
        warnings: List[str],
    ) -> None:
        # Basic keyword heuristic for acceptance criteria
        keywords = [
            word.lower()
            for word in re.findall(r"\b\w{4,}\b", acceptance_criteria)
            if word.lower() not in {"must", "should", "will", "have", "that", "this", "with"}
        ]
        if keywords:
            matched = sum(1 for kw in keywords if kw in content.lower())
            match_ratio = matched / len(keywords)
            checks["acceptance_criteria_keyword_match"] = match_ratio > 0.3
            if match_ratio <= 0.3:
                warnings.append("Output may not fully address the acceptance criteria.")


validator = OutputValidator()
