from azpipegen.extract import extract


def test_python_pytest_webapp_deploy():
    spec = extract(
        "Build a Python 3.11 app, run pytest, then deploy to an Azure Web App called my-api "
        "on push to main"
    )
    assert spec.language == "python"
    assert spec.python_version == "3.11"
    assert spec.test_framework == "pytest"
    assert spec.deploy_target == "azure-webapp"
    assert spec.trigger_branches == ["main"]
    assert not spec.uncertainties


def test_node_jest_aks_deploy_with_lint():
    spec = extract(
        "Node.js 20 project, install with npm, run eslint and jest, deploy to AKS on merge to "
        "main and release"
    )
    assert spec.language == "node"
    assert spec.node_version == "20.x"
    assert spec.test_framework == "jest"
    assert spec.lint is True
    assert spec.deploy_target == "aks"
    assert "main" in spec.trigger_branches


def test_dotnet_build_only_no_deploy():
    spec = extract("Build and test a .NET 8 solution with dotnet test, no deployment needed")
    assert spec.language == "dotnet"
    assert spec.test_framework == "dotnet-test"
    assert spec.deploy_target == "none"


def test_unrecognized_language_flags_uncertainty():
    spec = extract("Compile the thing and ship it somewhere")
    assert spec.language == "python"  # default
    assert any("language" in note.lower() for note in spec.uncertainties)


def test_deploy_mentioned_but_target_unrecognized_flags_uncertainty():
    spec = extract("Python app with pytest, deploy it to our server after tests pass")
    assert spec.deploy_target == "none"
    assert any("deploy" in note.lower() for note in spec.uncertainties)


def test_docker_build():
    spec = extract("Containerize the app with Docker and build the image, no tests")
    assert spec.language == "docker"
    assert spec.test_framework is None
