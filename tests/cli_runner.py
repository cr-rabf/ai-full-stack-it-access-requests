"""Run the real CLI in a subprocess with networking and credential reads blocked."""
import os
from pathlib import Path
import socket
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_mock_provider import NoCredentials

with mock.patch.object(os, "environ", NoCredentials()), \
     mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
     mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
    from access_requests.cli import main
    raise SystemExit(main())
