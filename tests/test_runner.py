from linux_diag_kit.runner import run_command


def test_run_command_success():
    res = run_command(["python3", "-c", "print('ok')"])
    assert res.ok
    assert res.returncode == 0
    assert res.stdout.strip() == "ok"


def test_run_command_dry_run():
    res = run_command(["rm", "-rf", "/nonexistent"], dry_run=True)
    assert res.dry_run
    assert res.ok
    assert res.returncode == 0


def test_run_command_timeout():
    res = run_command(["python3", "-c", "import time; time.sleep(2)"], timeout=0.1)
    assert not res.ok
    assert res.returncode == 124
    assert "timed out" in res.stderr.lower()
