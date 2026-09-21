"""Interleaved events must not extend a synchronous request's deadline."""

import socket
import struct
import unittest
from collections import deque
from unittest.mock import Mock, patch

from orbit3d_hub.client import Client
from orbit3d_hub.protocol import Message, MessageType


class ClientDeadlineTests(unittest.TestCase):
    def test_events_do_not_restart_request_timeout(self):
        clock = [0.0]
        waits = []
        client = Client.__new__(Client)
        connection = Mock()
        client._socket = connection
        client._timeout = 0.1
        client._next_request_id = 1
        client._pending_events = deque()

        def receive(_connection, timeout):
            waits.append(timeout)
            clock[0] += 0.06
            return Message(
                MessageType.MOTION_EVENT, 0, struct.pack(">IQ6i", 1, 0, 1, 0, 0, 0, 0, 0)
            )

        client._reader = Mock(receive=receive)
        with patch("orbit3d_hub.client.time.monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(socket.timeout):
                client.list_devices()
        self.assertEqual(len(waits), 2)
        self.assertAlmostEqual(waits[0], 0.1)
        self.assertAlmostEqual(waits[1], 0.04)
        connection.close.assert_called_once()
        self.assertIsNone(client._socket)


if __name__ == "__main__":
    unittest.main()
