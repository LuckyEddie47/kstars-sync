import termios
from unittest.mock import MagicMock, patch

from kstars_sync.main import main, wait_for_exit


@patch("kstars_sync.main.wait_for_exit")
@patch("kstars_sync.main.run_workflow", return_value=0)
@patch("kstars_sync.main.load_config")
def test_main_success(mock_load_cfg, mock_run_wf, mock_wait):
    mock_cfg = MagicMock()
    mock_load_cfg.return_value = mock_cfg

    with patch("sys.exit") as mock_exit:
        main()

    mock_load_cfg.assert_called_once()
    mock_run_wf.assert_called_once_with(mock_cfg)
    mock_wait.assert_called_once()
    mock_exit.assert_called_once_with(0)


@patch("kstars_sync.main.wait_for_exit")
@patch("kstars_sync.main.run_workflow", return_value=1)
@patch("kstars_sync.main.load_config")
def test_main_error_exit_code(mock_load_cfg, mock_run_wf, mock_wait):
    mock_cfg = MagicMock()
    mock_load_cfg.return_value = mock_cfg

    with patch("sys.exit") as mock_exit:
        main()

    mock_wait.assert_called_once()
    mock_exit.assert_called_once_with(1)


def test_wait_for_exit_noninteractive_does_not_read(capsys):
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = False

    with patch("kstars_sync.main.sys.stdin", fake_stdin):
        wait_for_exit()

    output = capsys.readouterr().out
    assert "kstars-sync completed, press any key to exit..." in output
    fake_stdin.read.assert_not_called()


def test_wait_for_exit_interactive_reads_one_key():
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True
    fake_stdin.fileno.return_value = 10
    fake_stdin.read.return_value = "x"

    original_settings = MagicMock()

    with patch("kstars_sync.main.sys.stdin", fake_stdin), patch(
        "kstars_sync.main.termios.tcgetattr",
        return_value=original_settings,
    ) as mock_getattr, patch(
        "kstars_sync.main.tty.setraw"
    ) as mock_setraw, patch(
        "kstars_sync.main.termios.tcsetattr"
    ) as mock_setattr:
        wait_for_exit()

    mock_getattr.assert_called_once_with(10)
    mock_setraw.assert_called_once_with(10)
    fake_stdin.read.assert_called_once_with(1)
    mock_setattr.assert_called_once_with(
        10,
        termios.TCSADRAIN,
        original_settings,
    )
