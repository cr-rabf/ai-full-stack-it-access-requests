"""Run the real CLI in a subprocess with networking and credential reads blocked."""
import os
from pathlib import Path
import socket
import sys
import runpy
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.argv[1:2] != ["--installed-module"]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_mock_provider import NoCredentials

with mock.patch.object(os, "environ", NoCredentials()), \
     mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
     mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
    if sys.argv[1:2] == ["--installed-module"]:
        import importlib.util
        spec = importlib.util.find_spec("access_request")
        assert spec is not None and Path(spec.origin).is_relative_to(Path(sys.prefix) / "lib/access-requests")
        sys.argv = ["access_request"] + sys.argv[2:]
        runpy.run_module("access_request", run_name="__main__", alter_sys=True)
    elif sys.argv[1:2] == ["--installed"]:
        launcher = sys.argv[2]
        sys.argv = [launcher] + sys.argv[3:]
        runpy.run_path(launcher, run_name="__main__")
    else:
        from src.cli import main
        raise SystemExit(main())
