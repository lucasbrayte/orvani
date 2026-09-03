
from libreoffice_sync.main import build_parser


def test_cli_exposes_expected_commands():
    parser = build_parser()
    for command in ("health", "run", "init-workbook"):
        args = parser.parse_args([command])
        assert args.command == command
