"""Deterministic, zero-config extraction of a PipelineSpec from a natural-language description.

This is the part of azpipegen that always works, with no API key and no network
call: a set of keyword/regex rules that read like "if they mention pytest, this
is a Python project that tests with pytest." It deliberately stays simple and
readable rather than clever, because every rule here is something a human can
audit and every miss becomes one line in `spec.uncertainties` instead of a
silent wrong guess.
"""

from __future__ import annotations

import re

from azpipegen.spec import PipelineSpec

_LANGUAGE_KEYWORDS = {
    "python": ["python", "pytest", "pip", "django", "flask", "fastapi", "poetry"],
    "node": ["node", "node.js", "nodejs", "npm", "yarn", "pnpm", "jest", "react", "vue", "express", "typescript"],
    "dotnet": [".net", "dotnet", "c#", "csharp", "nunit", "xunit", "asp.net"],
    "docker": ["docker", "dockerfile", "container image", "containerize"],
}

_TEST_FRAMEWORK_KEYWORDS = {
    "pytest": ["pytest"],
    "unittest": ["unittest"],
    "jest": ["jest"],
    "mocha": ["mocha"],
    "dotnet-test": ["dotnet test", "nunit", "xunit"],
}

_PACKAGE_MANAGER_BY_LANGUAGE = {
    "python": "pip",
    "node": "npm",
    "dotnet": "dotnet",
    "docker": None,
}

_DEPLOY_KEYWORDS = {
    "azure-webapp": ["web app", "webapp", "app service"],
    "aks": ["aks", "kubernetes", "k8s"],
    "functions": ["azure function", "function app", "functions app", "serverless"],
}

_LINT_KEYWORDS = ["lint", "flake8", "eslint", "pylint", "black", "ruff"]

_BRANCH_PATTERN = re.compile(
    r"(?:on (?:push|merge)(?: to)?|trigger(?:s|ed)? (?:on|by))\s+([a-zA-Z0-9_/\-,\s]+?)(?:$|[.,;]| branch)",
    re.IGNORECASE,
)
_VERSION_PATTERN = re.compile(r"(python|node|\.net|dotnet)\s*(\d+(?:\.\d+)*)", re.IGNORECASE)


def _find_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _detect_language(text: str) -> str | None:
    scores = {lang: sum(1 for kw in kws if kw in text) for lang, kws in _LANGUAGE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _detect_test_framework(text: str, language: str) -> str | None:
    for framework, kws in _TEST_FRAMEWORK_KEYWORDS.items():
        if _find_any(text, kws):
            return framework
    if "test" in text:
        # They asked for tests but didn't name a framework -> pick the
        # conventional default for the detected language rather than guessing wrong.
        return {"python": "pytest", "node": "jest", "dotnet": "dotnet-test"}.get(language)
    return None


def _detect_deploy_target(text: str) -> str:
    for target, kws in _DEPLOY_KEYWORDS.items():
        if _find_any(text, kws):
            return target
    return "none"


def _detect_branches(text: str) -> list[str] | None:
    match = _BRANCH_PATTERN.search(text)
    if not match:
        return None
    raw = match.group(1)
    branches = [b.strip() for b in re.split(r"[,/]| and ", raw) if b.strip()]
    # Guard against the regex accidentally swallowing trailing prose.
    branches = [b for b in branches if len(b) <= 40 and " " not in b]
    return branches or None


def _detect_versions(text: str, spec: PipelineSpec) -> None:
    for match in _VERSION_PATTERN.finditer(text):
        lang_token, version = match.group(1).lower(), match.group(2)
        if lang_token == "python":
            spec.python_version = version
        elif lang_token == "node":
            spec.node_version = version if "." in version else f"{version}.x"
        elif lang_token in (".net", "dotnet"):
            spec.dotnet_version = version if version.count(".") >= 1 else f"{version}.0.x"


def extract(description: str) -> PipelineSpec:
    """Parse a free-text pipeline description into a PipelineSpec.

    Never raises: an input we can't confidently parse just produces a spec
    with sensible defaults (Python, no deploy step) plus entries in
    `uncertainties` explaining what we guessed at or ignored.
    """
    text = description.lower()
    spec = PipelineSpec()
    uncertainties: list[str] = []

    language = _detect_language(text)
    if language:
        spec.language = language
    else:
        uncertainties.append(
            "Couldn't detect a language/stack from the description; defaulted to Python. "
            "Mention 'Python', 'Node', '.NET', or 'Docker' explicitly for a better result."
        )

    spec.package_manager = _PACKAGE_MANAGER_BY_LANGUAGE.get(spec.language)

    test_framework = _detect_test_framework(text, spec.language)
    if test_framework:
        spec.test_framework = test_framework
    elif "test" in text:
        uncertainties.append("Mentioned tests but no framework was recognized; no test step was added.")

    spec.lint = _find_any(text, _LINT_KEYWORDS)

    spec.deploy_target = _detect_deploy_target(text)
    if spec.deploy_target == "none" and any(w in text for w in ("deploy", "release", "publish")):
        uncertainties.append(
            "Mentioned a deploy step but the target wasn't recognized (expected web app / AKS / function app); "
            "no deploy stage was added."
        )

    branches = _detect_branches(text)
    if branches:
        spec.trigger_branches = branches

    _detect_versions(text, spec)

    spec.uncertainties = uncertainties
    return spec
