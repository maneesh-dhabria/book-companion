"""QuizPromptBuilder — renders the question/grade/explain/rollup prompts.

Reuses the Jinja2 FileSystemLoader pattern from SummarizerService but loads
templates from `backend/app/templates/quiz/` (a top-level templates dir, not
service-local, so other services can borrow templates if needed).
"""

from pathlib import Path

import jinja2

from app.config import Settings
from app.services.quiz.token_counter import count_tokens

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "quiz"


class QuizPromptBuilder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )

    def _render(self, template_name: str, **ctx) -> str:
        return self._env.get_template(template_name).render(**ctx)

    def build_generation_prompt(
        self,
        *,
        scope_content: str,
        recent_stems: list[str],
        themed_summary: str | None,
        theme: str | None,
        shape_histogram: dict[str, int],
        skipped_concepts: list[str],
        max_prompt_tokens: int | None = None,
        validator_error: str | None = None,
    ) -> str:
        shape_targets = self.settings.quiz.shape_target_distribution
        ctx = dict(
            scope_content=scope_content,
            recent_stems=recent_stems,
            themed_summary=themed_summary,
            theme=theme,
            shape_histogram=shape_histogram,
            skipped_concepts=skipped_concepts,
            shape_targets=shape_targets,
            validator_error=validator_error,
        )
        prompt = self._render("question.j2", **ctx)
        if max_prompt_tokens is None or count_tokens(prompt) <= max_prompt_tokens:
            return prompt

        # Budget enforcement — truncate scope_content from the end (preserve
        # headers + structured context above). Binary-search the cut point so
        # we don't pay an O(n) re-render per character.
        lo, hi = 0, len(scope_content)
        best = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = scope_content[:mid]
            ctx["scope_content"] = candidate
            rendered = self._render("question.j2", **ctx)
            if count_tokens(rendered) <= max_prompt_tokens:
                best = rendered
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def build_grading_prompt(
        self,
        *,
        stem: str,
        citation: str,
        user_answer: str,
        append_fatigue_prompt: bool = False,
    ) -> str:
        prompt = self._render(
            "grade.j2",
            stem=stem,
            citation=citation,
            user_answer=user_answer,
            append_fatigue_prompt=append_fatigue_prompt,
        )
        if append_fatigue_prompt and "Want to keep going or wrap up here?" not in prompt:
            # Defensive: spec FR-50 requires the literal phrase. The template
            # does emit it, but if a future template edit drops it, surface
            # the failure here rather than silently shipping a degraded prompt.
            prompt += "\n\nWant to keep going or wrap up here?"
        return prompt

    def build_explain_prompt(
        self,
        *,
        stem: str,
        citation: str,
        prior_explains: list[str] | None = None,
    ) -> str:
        return self._render(
            "explain.j2",
            stem=stem,
            citation=citation,
            prior_explains=prior_explains or [],
        )

    def build_rollup_prompt(
        self,
        *,
        stems: list[str],
        max_chars: int | None = None,
    ) -> str:
        return self._render(
            "rollup.j2",
            stems=stems,
            max_chars=max_chars or self.settings.quiz.theme_max_chars,
        )
