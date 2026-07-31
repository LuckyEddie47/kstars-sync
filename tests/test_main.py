from unittest.mock import MagicMock, patch

from kstars_sync.main import main


@patch("kstars_sync.main.run_workflow", return_value=0)
@patch("kstars_sync.main.load_config")
def test_main_success(mock_load_cfg, mock_run_wf):
    mock_cfg = MagicMock()
    mock_load_cfg.return_value = mock_cfg

    with patch("sys.exit") as mock_exit:
        main()

    mock_load_cfg.assert_called_once()
    mock_run_wf.assert_called_once_with(mock_cfg)
    mock_exit.assert_called_once_with(0)


@patch("kstars_sync.main.run_workflow", return_value=1)
@patch("kstars_sync.main.load_config")
def test_main_error_exit_code(mock_load_cfg, mock_run_wf):
    mock_cfg = MagicMock()
    mock_load_cfg.return_value = mock_cfg

    with patch("sys.exit") as mock_exit:
        main()

    mock_exit.assert_called_once_with(1)