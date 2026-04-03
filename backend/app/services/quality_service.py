"""Extraction quality validation — deterministic heuristics, no LLM calls."""

import re
from dataclasses import dataclass


@dataclass
class QualityIssue:
    section_index: int
    section_title: str
    check: str
    severity: str  # "error", "warning", "info"
    message: str
    suggested_action: str


NON_CONTENT_PATTERN = re.compile(
    r"^(copyright|about the authors?|also by|acknowledgments?|dedication|"
    r"table of contents|index|bibliography)$",
    re.IGNORECASE,
)

PAGE_NUMBER_PATTERN = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)


class QualityService:
    def check_sections(self, sections: list[dict]) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        for i, s in enumerate(sections):
            issues.extend(self._check_section(s, sections))
        severity_order = {"error": 0, "warning": 1, "info": 2}
        issues.sort(key=lambda x: severity_order.get(x.severity, 3))
        return issues

    def suggested_actions(self, issues: list[QualityIssue]) -> list[str]:
        actions = []
        delete_indices = [i.section_index for i in issues if i.suggested_action == "delete" and i.severity in ("error", "warning")]
        if delete_indices:
            idx_str = ", ".join(str(i) for i in delete_indices)
            reasons = set(i.check for i in issues if i.section_index in delete_indices)
            actions.append(f"Delete sections {idx_str} — detected as {', '.join(reasons)}")
        for issue in issues:
            if issue.suggested_action.startswith("merge") and issue.severity == "warning":
                actions.append(f"Merge section {issue.section_index} into adjacent — {issue.message}")
        return actions

    def _check_section(self, section: dict, all_sections: list[dict]) -> list[QualityIssue]:
        issues = []
        idx = section["index"]
        title = section["title"]
        content = section.get("content", "")
        char_count = len(content)
        depth = section.get("depth", 0)

        if char_count == 0:
            issues.append(QualityIssue(idx, title, "empty", "error", "0 characters", "delete"))
            return issues

        if char_count < 200:
            issues.append(QualityIssue(idx, title, "short", "warning", f"{char_count} chars — possibly truncated", "merge into adjacent section"))

        if NON_CONTENT_PATTERN.match(title.strip()):
            issues.append(QualityIssue(idx, title, "non-content", "warning", "Title matches non-content pattern", "delete"))

        if char_count < 200:
            for other in all_sections:
                if other["index"] != idx and other.get("depth") == depth:
                    if len(other.get("content", "")) >= char_count * 5:
                        issues.append(QualityIssue(idx, title, "truncated", "warning", f"{char_count} chars — adjacent section has {len(other['content'])} chars", "merge into adjacent"))
                        break

        if char_count < 500 and depth > 0:
            issues.append(QualityIssue(idx, title, "tiny_fragment", "warning", f"{char_count} chars at depth {depth}", "merge into parent"))

        if char_count > 100_000:
            issues.append(QualityIssue(idx, title, "oversized", "info", f"{char_count:,} chars — consider splitting", "split at detected sub-headings"))

        replacement_count = content.count("\ufffd")
        if char_count > 0 and replacement_count / char_count > 0.01:
            issues.append(QualityIssue(idx, title, "encoding_issues", "warning", f"{replacement_count} replacement characters ({replacement_count/char_count:.1%})", "flag for review"))

        for other in all_sections:
            if other["index"] <= idx:
                continue
            similarity = self._trigram_jaccard(content, other.get("content", ""))
            if similarity > 0.8:
                shorter = idx if char_count <= len(other.get("content", "")) else other["index"]
                issues.append(QualityIssue(shorter, title, "repeated_content", "warning", f">{similarity:.0%} overlap with section {other['index']}", "delete the shorter duplicate"))

        image_count = section.get("image_count", 0)
        if image_count > 0 and char_count > 0:
            if image_count * 5000 > char_count * 3:
                issues.append(QualityIssue(idx, title, "image_heavy", "info", f"{image_count} images for {char_count:,} chars of text", "flag for review"))

        page_matches = PAGE_NUMBER_PATTERN.findall(content)
        if len(page_matches) > 3:
            issues.append(QualityIssue(idx, title, "page_numbers", "info", f"{len(page_matches)} isolated page numbers detected", "flag for review"))

        return issues

    @staticmethod
    def _trigram_jaccard(text_a: str, text_b: str) -> float:
        if len(text_a) < 3 or len(text_b) < 3:
            return 0.0
        trigrams_a = set(text_a[i:i+3] for i in range(len(text_a) - 2))
        trigrams_b = set(text_b[i:i+3] for i in range(len(text_b) - 2))
        intersection = trigrams_a & trigrams_b
        union = trigrams_a | trigrams_b
        return len(intersection) / len(union) if union else 0.0
