import yaml

from azpipegen.extract import extract
from azpipegen.render import RenderError, render
from azpipegen.spec import PipelineSpec


def _parse(yaml_text: str) -> dict:
    # Strip the leading `#` comment header before parsing, then confirm the
    # whole file (header included) is still valid YAML end to end.
    parsed_whole = yaml.safe_load(yaml_text)
    assert parsed_whole is not None
    return parsed_whole


def test_render_produces_valid_yaml_with_build_and_deploy_stages():
    spec = extract(
        "Build a Python 3.12 app, run pytest, then deploy to an Azure Web App called demo-app "
        "on push to main"
    )
    yaml_text = render(spec)
    doc = _parse(yaml_text)

    assert doc["trigger"]["branches"]["include"] == ["main"]
    stage_names = [s["stage"] for s in doc["stages"]]
    assert stage_names == ["Build", "Deploy"]
    assert "pool" not in doc  # moved onto stages/jobs once there's a Deploy stage

    build_steps = doc["stages"][0]["jobs"][0]["steps"]
    assert any(step.get("task") == "UsePythonVersion@0" for step in build_steps)
    assert any("pytest" in step.get("script", "") for step in build_steps)


def test_render_build_only_keeps_single_stage_and_top_level_pool():
    spec = extract("Build and test a .NET 8 solution with dotnet test, no deployment needed")
    yaml_text = render(spec)
    doc = _parse(yaml_text)

    assert [s["stage"] for s in doc["stages"]] == ["Build"]
    assert doc["pool"]["vmImage"] == "ubuntu-latest"


def test_render_includes_uncertainty_notes_as_comments():
    spec = extract("Compile the thing and ship it somewhere")
    yaml_text = render(spec)
    assert "# NOTE:" in yaml_text
    assert "language" in yaml_text.lower()


def test_render_rejects_invalid_spec():
    spec = PipelineSpec(language="cobol")
    try:
        render(spec)
        assert False, "expected RenderError"
    except RenderError as exc:
        assert "cobol" in str(exc)


def test_render_lint_step_present_when_requested():
    spec = extract("Node project, run eslint, jest tests, no deploy")
    yaml_text = render(spec)
    doc = _parse(yaml_text)
    steps = doc["stages"][0]["jobs"][0]["steps"]
    assert any("eslint" in step.get("script", "") for step in steps)
