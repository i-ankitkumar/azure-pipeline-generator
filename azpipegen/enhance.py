"""Optional AI pass: hand Claude the original description plus the deterministic draft,
and let it fix exactly the things the rule-based extractor flagged as uncertain.

Design intent, same as tfscan/explain.py in the sibling project: the deterministic
path (extract.py + render.py) is fast, free, and reproducible, and always produces a
valid pipeline on its own. This layer never invents structure from scratch — it is
strictly an editing pass over that output, gated behind ANTHROPIC_API_KEY, and it
fails soft (falls back to the deterministic draft) on any error.
"""

from __future__ import annotations

import os

from azpipegen.spec import PipelineSpec

_PROMPT_TEMPLATE = """You are a senior Azure DevOps engineer. A teammate described the CI/CD \
pipeline they want, and a rule-based tool produced a first-draft azure-pipelines.yml from it. \
Improve the draft so it fully matches the description, fixing only what the draft's own notes \
flag as uncertain or missing. Keep everything the draft already got right unchanged.

Original description:
{description}

Draft azure-pipelines.yml:
{draft_yaml}

Known gaps in the draft:
{uncertainties}

Return ONLY the corrected YAML file content — no markdown fences, no commentary."""


def enhance(description: str, draft_yaml: str, spec: PipelineSpec) -> str | None:
    """Return an improved YAML string, or None if enhancement isn't available/failed.

    Callers should fall back to `draft_yaml` when this returns None.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    uncertainties = "\n".join(f"- {u}" for u in spec.uncertainties) or "- none noted"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.environ.get("AZPIPEGEN_MODEL", "claude-sonnet-4-5"),
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT_TEMPLATE.format(
                        description=description,
                        draft_yaml=draft_yaml,
                        uncertainties=uncertainties,
                    ),
                }
            ],
        )
        text = response.content[0].text.strip()
        # Defensive: strip an accidental markdown fence if the model adds one anyway.
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        return text.strip() + "\n"
    except Exception:
        return None
