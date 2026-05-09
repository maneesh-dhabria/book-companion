"""Strict JSON schemas for quiz LLM round-trips (FR-30, FR-50, FR-62).

These schemas are passed to the LLM provider via `--json-schema` (Claude) or
`--output-schema` (Codex). Every schema sets `additionalProperties: false`
and uses JSON Schema `if/then` to make shape-conditional fields required at
parse time, so the validator catches missing `mcq_options` or
`intended_error` before the response ever reaches the spot-error invariant
validator.
"""

QUESTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["stem", "concept_label", "citation", "shape", "bloom_level"],
    "properties": {
        "stem": {"type": "string", "minLength": 1},
        "concept_label": {"type": "string", "minLength": 1},
        "citation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["section_id", "section_title", "snippet"],
            "properties": {
                "section_id": {"type": "integer"},
                "section_title": {"type": "string"},
                "snippet": {"type": "string"},
            },
        },
        "shape": {"enum": ["mcq", "open", "spot_error"]},
        "bloom_level": {
            "enum": [
                "remember",
                "understand",
                "apply",
                "analyze",
                "evaluate",
                "create",  # G21
            ]
        },
        "mcq_options": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 4,
            "maxItems": 4,
        },
        "mcq_correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
        "intended_error": {"type": "string"},
        "error_explanation": {"type": "string"},
    },
    "allOf": [
        {
            "if": {"properties": {"shape": {"const": "mcq"}}, "required": ["shape"]},
            "then": {"required": ["mcq_options", "mcq_correct_index"]},
        },
        {
            "if": {"properties": {"shape": {"const": "spot_error"}}, "required": ["shape"]},
            "then": {"required": ["intended_error", "error_explanation"]},
        },
    ],
}


FEEDBACK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["feedback", "agent_verdict"],
    "properties": {
        "feedback": {"type": "string", "minLength": 1},
        "agent_verdict": {"enum": ["correct", "partial", "incorrect"]},
    },
}


ROLLUP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["themes_summary"],
    "properties": {
        "themes_summary": {"type": "string"},
    },
}
