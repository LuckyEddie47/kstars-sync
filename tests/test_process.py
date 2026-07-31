import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kstars_sync.process import (
    CompletedApplication,
    ProcessError,
    find_process,
    is_running,
    run_application,
)


def test_current_python_is_running():
    info = find_process(sys.executable)

    assert info is not None
    assert info.executable == Path(sys.executable).resolve()


def test_python_is_running():
    assert is_running(sys.executable)


def test_missing_executable():
    assert not is_running("/this/does/not/exist")


def test_run_application_success():
    mock_process = MagicMock()
    mock_process.wait.return_value = 0

    with patch(
        "subprocess.Popen",
        return_value=mock_process,
    ) as popen:

        result = run_application("/usr/bin/example")

    popen.assert_called_once_with(
        ["/usr/bin/example"]
    )

    assert result == CompletedApplication(
        returncode=0
    )


def test_run_application_nonzero_exit():
    mock_process = MagicMock()
    mock_process.wait.return_value = 42

    with patch(
        "subprocess.Popen",
        return_value=mock_process,
    ):

        result = run_application("/usr/bin/example")

    assert result.returncode == 42


def test_run_application_start_failure():
    with patch(
        "subprocess.Popen",
        side_effect=OSError("boom"),
    ):

        with pytest.raises(ProcessError):
            run_application("/usr/bin/example")