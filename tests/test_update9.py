"""Update 9: the deploy step survives a brief DNS hiccup on the runner."""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pipeline.yml"


def _deploy_step() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("- name: Deploy")
    return text[start:]


def test_lftp_install_is_retried():
    step = _deploy_step()
    assert "for attempt in 1 2 3 4 5" in step
    assert "Acquire::Retries=3" in step
    assert "command -v lftp" in step
    # the old single-shot install is gone
    assert "apt-get -qq update && sudo apt-get -qq install" not in step


def test_retry_loop_comes_before_upload():
    step = _deploy_step()
    assert step.index("for attempt in") < step.index("lftp --env-password")


def test_data_is_committed_before_deploy():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.index("- name: Commit data") < text.index("- name: Deploy")
