"""The normalized, structured description of a pipeline.

Everything downstream (template rendering, the optional AI enhancement pass)
works off this dataclass rather than raw text, so the two "front ends" — the
deterministic keyword extractor and, in future, any other input method — just
need to agree on producing a PipelineSpec.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VALID_LANGUAGES = ("python", "node", "dotnet", "docker")
VALID_DEPLOY_TARGETS = ("azure-webapp", "aks", "functions", "none")


@dataclass
class PipelineSpec:
    language: str = "python"
    package_manager: str | None = None          # e.g. "pip", "npm", "dotnet"
    test_framework: str | None = None            # e.g. "pytest", "jest", "dotnet-test"
    lint: bool = False
    deploy_target: str = "none"
    deploy_service_connection: str = "<service-connection-name>"
    app_name: str = "<app-name>"
    trigger_branches: list[str] = field(default_factory=lambda: ["main"])
    pool_vm_image: str = "ubuntu-latest"
    python_version: str = "3.11"
    node_version: str = "20.x"
    dotnet_version: str = "8.0.x"

    # Free-text notes the extractor couldn't confidently turn into a field.
    # Surfaced in the YAML as a comment, and handed to the AI enhancer (when
    # enabled) so it has a chance to act on them.
    uncertainties: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors = []
        if self.language not in VALID_LANGUAGES:
            errors.append(f"Unknown language '{self.language}' (expected one of {VALID_LANGUAGES})")
        if self.deploy_target not in VALID_DEPLOY_TARGETS:
            errors.append(f"Unknown deploy target '{self.deploy_target}' (expected one of {VALID_DEPLOY_TARGETS})")
        return errors
