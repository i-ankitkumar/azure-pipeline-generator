"""Stage templates: each function returns a list of YAML step dicts for one concern.

Keeping these as plain Python (building dicts, dumped once at the end by
render.py) rather than string-concatenated YAML means we can never emit
invalid indentation — yaml.safe_dump does the formatting, we just decide
structure.
"""

from __future__ import annotations

from azpipegen.spec import PipelineSpec


def build_steps(spec: PipelineSpec) -> list[dict]:
    if spec.language == "python":
        steps = [
            {
                "task": "UsePythonVersion@0",
                "inputs": {"versionSpec": spec.python_version},
                "displayName": f"Use Python {spec.python_version}",
            },
            {
                "script": "python -m pip install --upgrade pip\npip install -r requirements.txt",
                "displayName": "Install dependencies",
            },
        ]
    elif spec.language == "node":
        steps = [
            {
                "task": "NodeTool@0",
                "inputs": {"versionSpec": spec.node_version},
                "displayName": f"Use Node.js {spec.node_version}",
            },
            {"script": "npm ci", "displayName": "Install dependencies"},
            {"script": "npm run build --if-present", "displayName": "Build"},
        ]
    elif spec.language == "dotnet":
        steps = [
            {
                "task": "UseDotNet@2",
                "inputs": {"packageType": "sdk", "version": spec.dotnet_version},
                "displayName": f"Use .NET SDK {spec.dotnet_version}",
            },
            {"script": "dotnet restore", "displayName": "Restore"},
            {"script": "dotnet build --configuration Release", "displayName": "Build"},
        ]
    else:  # docker
        steps = [
            {
                "task": "Docker@2",
                "inputs": {
                    "command": "build",
                    "repository": spec.app_name,
                    "dockerfile": "**/Dockerfile",
                    "tags": "$(Build.BuildId)",
                },
                "displayName": "Build Docker image",
            }
        ]
    return steps


def lint_steps(spec: PipelineSpec) -> list[dict]:
    if not spec.lint:
        return []
    commands = {
        "python": "pip install ruff\nruff check .",
        "node": "npx eslint .",
        "dotnet": "dotnet format --verify-no-changes",
        "docker": "docker run --rm -i hadolint/hadolint < Dockerfile",
    }
    return [{"script": commands.get(spec.language, "echo 'no linter configured'"), "displayName": "Lint"}]


def test_steps(spec: PipelineSpec) -> list[dict]:
    if not spec.test_framework:
        return []
    if spec.test_framework == "pytest":
        return [
            {"script": "pip install pytest pytest-azurepipelines\npytest", "displayName": "Run tests (pytest)"}
        ]
    if spec.test_framework == "unittest":
        return [{"script": "python -m unittest discover", "displayName": "Run tests (unittest)"}]
    if spec.test_framework == "jest":
        return [{"script": "npx jest --ci", "displayName": "Run tests (jest)"}]
    if spec.test_framework == "mocha":
        return [{"script": "npx mocha", "displayName": "Run tests (mocha)"}]
    if spec.test_framework == "dotnet-test":
        return [{"script": "dotnet test --configuration Release", "displayName": "Run tests (dotnet test)"}]
    return []


def deploy_stage(spec: PipelineSpec) -> dict | None:
    """A full Stage (not just steps) since deploy conventionally runs after a Build stage."""
    if spec.deploy_target == "none":
        return None

    if spec.deploy_target == "azure-webapp":
        deploy_steps = [
            {
                "task": "AzureWebApp@1",
                "inputs": {
                    "azureSubscription": spec.deploy_service_connection,
                    "appType": "webAppLinux" if spec.language != "dotnet" else "webApp",
                    "appName": spec.app_name,
                    "package": "$(Pipeline.Workspace)/drop/**/*.zip",
                },
                "displayName": f"Deploy to Azure Web App '{spec.app_name}'",
            }
        ]
    elif spec.deploy_target == "aks":
        deploy_steps = [
            {
                "task": "KubernetesManifest@1",
                "inputs": {
                    "action": "deploy",
                    "kubernetesServiceConnection": spec.deploy_service_connection,
                    "manifests": "manifests/deployment.yaml",
                },
                "displayName": "Deploy to AKS",
            }
        ]
    elif spec.deploy_target == "functions":
        deploy_steps = [
            {
                "task": "AzureFunctionApp@2",
                "inputs": {
                    "azureSubscription": spec.deploy_service_connection,
                    "appType": "functionApp",
                    "appName": spec.app_name,
                    "package": "$(Pipeline.Workspace)/drop/**/*.zip",
                },
                "displayName": f"Deploy to Azure Function App '{spec.app_name}'",
            }
        ]
    else:
        return None

    return {
        "stage": "Deploy",
        "displayName": "Deploy",
        "dependsOn": "Build",
        "condition": "succeeded()",
        "jobs": [
            {
                "deployment": "DeployJob",
                "displayName": "Deploy",
                "pool": {"vmImage": spec.pool_vm_image},
                "environment": spec.app_name,
                "strategy": {"runOnce": {"deploy": {"steps": deploy_steps}}},
            }
        ],
    }
