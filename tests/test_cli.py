import subprocess

def test_cli_help():
    """CLI module imports and has a main function."""
    from hermesfy.cli.main import main
    assert callable(main)

def test_cli_list_models():
    """CLI module is importable and has builder/commands."""
    from hermesfy.cli.main import build_parser, main
    assert callable(build_parser)
    assert callable(main)
