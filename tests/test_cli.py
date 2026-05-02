import subprocess

def test_cli_help():
    result = subprocess.run(['python3', '-m', 'hermesfy.cli', '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage" in result.stdout

def test_cli_list_models():
    result = subprocess.run(['env', 'PYTHONPATH=src', 'python3', '-m', 'hermesfy.cli', '--list-models'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "flux" in result.stdout
