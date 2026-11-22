"""Update 11: the FTP certificate pin is a repo variable with a checked default."""
import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pipeline.yml"
NEW_PIN = "9A:60:84:AA:10:13:43:13:F8:70:F6:29:22:3A:63:35:56:F6:65:0B"
OLD_PIN = "AB:53:C4:34:26:DE:BD:C8:7F:F1:B9:A3:27:0E:28:6B:E2:20:77:35"


def _deploy() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text[text.index("- name: Deploy"):]


def test_pin_comes_from_variable_with_new_default():
    step = _deploy()
    assert "vars.FTP_CERT_SHA1" in step
    assert NEW_PIN in step
    assert OLD_PIN not in WORKFLOW.read_text(encoding="utf-8")
    assert "set ssl:verify-certificate/$FTP_CERT_SHA1 no;" in step


def test_pin_format_is_validated_before_upload():
    step = _deploy()
    check = step.index("FTP_CERT_SHA1\" =~")
    assert check < step.index("lftp --env-password")
    pattern = re.search(r'=~ (\^\(\[0-9A-F\]\{2\}:\)\{19\}\[0-9A-F\]\{2\}\$)', step).group(1)
    assert re.fullmatch(pattern, NEW_PIN)
    assert not re.fullmatch(pattern, "9A:60:84 no; !rm -rf /")


def test_tls_is_still_enforced():
    step = _deploy()
    for line in ("set ftp:ssl-force yes;", "set ftp:ssl-protect-data yes;", "set ftp:ssl-protect-list yes;"):
        assert line in step
    assert "verify-certificate no" not in step


def test_failed_upload_explains_the_fix():
    step = _deploy()
    assert "::error::Upload failed" in step and "FTP_CERT_SHA1" in step
