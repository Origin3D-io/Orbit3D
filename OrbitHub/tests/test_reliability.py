from __future__ import annotations

import os
import pathlib
import socket
import struct
import subprocess
import threading
import time
import unittest

from orbit3d_hub import (
    BUTTONS,
    MOTION,
    ButtonEvent,
    ButtonStateEvent,
    Client,
    InputReset,
    InputState,
    MotionEvent,
    Provider,
    select_device,
)
from orbit3d_hub.protocol import (
    HEADER,
    VERSION_MAJOR,
    VERSION_MINOR,
    MessageReader,
    MessageType,
    receive_message,
    send_message,
    text,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = pathlib.Path(os.environ.get("ORBIT_HUB_TEST_BIN_DIR", ROOT / "build"))


class PacketTests(unittest.TestCase):
    def test_minor_version_mismatch_reports_protocol_version(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.sendall(HEADER.pack(b"O3DH", VERSION_MAJOR, VERSION_MINOR ^ 1, 1, 0, 1))
        with self.assertRaisesRegex(ValueError, "^Unsupported Orbit3D protocol version$"):
            receive_message(left)

    def test_fragmented_packet_survives_multiple_timeouts(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        reader = MessageReader()
        payload = struct.pack(">IQ6i", 1, 10, 1, 2, 3, 4, 5, 6)
        packet = HEADER.pack(b"O3DH", VERSION_MAJOR, VERSION_MINOR, 7, len(payload), 0) + payload
        for fragment in (packet[:8], packet[8:20]):
            right.sendall(fragment)
            with self.assertRaises(socket.timeout):
                reader.receive(left, 0.01)
        right.sendall(packet[20:])
        self.assertEqual(reader.receive(left, 0.1).payload, payload)

    def test_input_keeps_clicks_and_expires_motion(self):
        now = [0.0]
        state = InputState(clock=lambda: now[0])
        motion = MotionEvent(1, 1, 100, 0, 0, 0, 0, 0)
        state.accept(motion)
        state.accept(ButtonStateEvent(1, 2))
        state.accept(ButtonEvent(1, 2, 1, True))
        state.accept(ButtonEvent(1, 3, 1, False))
        events = state.take_buttons()
        self.assertEqual(len(events), 3)
        self.assertEqual([event.pressed for event in events[1:]], [True, False])
        self.assertEqual(state.sample(), motion)
        now[0] = 0.25
        self.assertIsNone(state.sample())
        state.reset()
        self.assertEqual(state.take_buttons(), [InputReset()])

    def test_motion_is_held_independent_of_provider_rate(self):
        def integrate(rate):
            now = [0.0]
            state = InputState(clock=lambda: now[0])
            distance = 0.0
            next_report = 0.0
            for tick in range(100):
                now[0] = tick / 100
                if now[0] >= next_report:
                    state.accept(MotionEvent(1, 0, 1000000, 0, 0, 0, 0, 0))
                    next_report += 1 / rate
                distance += state.sample().tx / 1000000 * 0.01
            return distance

        self.assertAlmostEqual(integrate(20), integrate(100))


class BrokerTests(unittest.TestCase):
    def setUp(self):
        exe = "orbithub.exe" if os.name == "nt" else "orbithub"
        self.server = subprocess.Popen(
            [str(BIN / exe), "--port", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_server)
        self.port = int(self.server.stdout.readline().split()[1])

    def stop_server(self):
        self.server.terminate()
        self.server.wait(timeout=3)
        self.server.stdout.close()
        self.server.stderr.close()

    def raw(self):
        conn = socket.create_connection(("127.0.0.1", self.port), timeout=1)
        self.addCleanup(conn.close)
        send_message(conn, MessageType.HELLO_REQUEST, 1)
        receive_message(conn)
        return conn

    @unittest.skipIf(os.name == "nt", "Windows console control events require an attached console")
    def test_termination_closes_clients_and_releases_port(self):
        conn = self.raw()
        self.server.terminate()
        self.assertEqual(self.server.wait(timeout=3), 0)
        self.assert_closed(conn)
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", self.port))

    def test_cli_version_and_invalid_ports(self):
        exe = str(BIN / ("orbithub.exe" if os.name == "nt" else "orbithub"))
        result = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertIn(f"OrbitHub 0.2.1 (protocol {VERSION_MAJOR}.{VERSION_MINOR})", result.stdout)
        for port in ("abc", "", "-1", "43120junk", "65536"):
            with self.subTest(port=port):
                result = subprocess.run([exe, "--port", port], capture_output=True, timeout=3)
                self.assertEqual(result.returncode, 2)

    def test_bad_identity_is_rejected_without_poisoning_enumeration(self):
        conn = self.raw()
        for vendor in (b"\xff", b"a\x00b", b"x" * 96, b"\xed\xa0\x80"):
            payload = struct.pack(">IB3xH", 1, 0, len(vendor)) + vendor + text("Test") + text("")
            send_message(conn, MessageType.PROVIDER_REGISTER_REQUEST, 2, payload)
            self.assertEqual(receive_message(conn).message_type, MessageType.ERROR)
        with Client(port=self.port) as client:
            self.assertEqual(client.list_devices(), [])

    def assert_closed(self, conn):
        conn.settimeout(4)
        try:
            self.assertEqual(conn.recv(1), b"")
        except ConnectionResetError:
            pass

    def test_invalid_headers_disconnect_only_the_sender(self):
        for magic, major, minor, size in (
            (b"BAD!", VERSION_MAJOR, VERSION_MINOR, 0),
            (b"O3DH", VERSION_MAJOR, VERSION_MINOR + 1, 0),
            (b"O3DH", VERSION_MAJOR, VERSION_MINOR, 65537),
        ):
            with self.subTest(magic=magic, minor=minor, size=size):
                conn = self.raw()
                conn.sendall(HEADER.pack(magic, major, minor, 1, size, 2))
                self.assert_closed(conn)
                with Client(port=self.port) as healthy:
                    self.assertEqual(healthy.list_devices(), [])

    def test_partial_packet_expires(self):
        conn = self.raw()
        conn.sendall(b"O3")
        self.assert_closed(conn)
        with Client(port=self.port) as healthy:
            self.assertEqual(healthy.list_devices(), [])

    def test_invalid_requests_cannot_extend_hello_deadline(self):
        with socket.create_connection(("127.0.0.1", self.port), timeout=1) as conn:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                try:
                    send_message(conn, MessageType.PING, 1)
                    self.assertEqual(receive_message(conn).message_type, MessageType.ERROR)
                except socket.timeout:
                    self.fail("Broker stopped responding without closing the connection")
                except (ConnectionError, OSError):
                    break
                time.sleep(0.05)
            else:
                self.fail("Invalid requests kept an ungreeted connection alive")
        with Client(port=self.port) as healthy:
            self.assertEqual(healthy.list_devices(), [])

    def test_connection_limit_preserves_existing_clients(self):
        clients = [self.raw() for _ in range(64)]
        with socket.create_connection(("127.0.0.1", self.port), timeout=1) as excess:
            self.assert_closed(excess)
        send_message(clients[0], MessageType.PING, 2)
        self.assertEqual(receive_message(clients[0]).message_type, MessageType.PONG)

    def test_malformed_requests_do_not_change_subscription(self):
        conn = self.raw()
        for payload in (b"", b"\x00" * 3, b"\x00" * 5):
            send_message(conn, MessageType.SUBSCRIBE_REQUEST, 2, payload)
            self.assertEqual(receive_message(conn).message_type, MessageType.ERROR)
        send_message(conn, MessageType.PING, 3)
        self.assertEqual(receive_message(conn).message_type, MessageType.PONG)

    def test_out_of_range_motion_disconnects_provider(self):
        with Provider(port=self.port) as provider:
            device = provider.register_device("Example", "Invalid Motion")
            payload = struct.pack(">IQ6i", device.device_id, 0, 1000001, 0, 0, 0, 0, 0)
            send_message(provider._socket, MessageType.PROVIDER_MOTION, 0, payload)
            self.assert_closed(provider._socket)
        with Client(port=self.port) as healthy:
            self.assertEqual(healthy.list_devices(), [])

    def test_held_button_snapshot_is_not_a_new_press(self):
        with Provider(port=self.port) as provider:
            device = provider.register_device("Example", "Device", "1", 32)
            provider.publish_button(device, 32, True)
            provider.ping()
            with Client(port=self.port) as client:
                client.subscribe(BUTTONS)
                self.assertEqual(
                    client.poll(timeout=1), ButtonStateEvent(device.device_id, 1 << 31)
                )
                provider.publish_button(device, 32, False)
                event = client.poll(timeout=1)
                self.assertIsInstance(event, ButtonEvent)
                self.assertFalse(event.pressed)

    def test_device_limit_and_explicit_selection(self):
        with Provider(port=self.port) as provider, Client(port=self.port) as client:
            for index in range(32):
                provider.register_device("Example", "Device", str(index))
            with self.assertRaises(RuntimeError):
                provider.register_device("Example", "Overflow")
            devices = client.list_devices()
            self.assertEqual(len(devices), 32)
            self.assertIsNone(select_device(devices))
            self.assertEqual(select_device(devices, "Example/Device/3").serial, "3")
            self.assertIsNone(select_device(devices, "Example/Device/missing"))
            self.assertIsNone(select_device([devices[0], devices[0]], "Example/Device/0"))

    def test_provider_cannot_publish_another_providers_device(self):
        with Provider(port=self.port) as owner, Provider(port=self.port) as other:
            device = owner.register_device("Owner", "Device")
            other.publish_motion(device, 1, 0, 0, 0, 0, 0)
            with self.assertRaises((OSError, ConnectionError, ValueError)):
                other.ping()
            owner.ping()

    def test_stale_provider_releases_held_buttons(self):
        with Provider(port=self.port) as provider, Client(port=self.port) as client:
            device = provider.register_device("Example", "Stale", button_count=1)
            client.subscribe(BUTTONS)
            client.poll(timeout=1)  # Initial state, not a click.
            provider.publish_button(device, 1, True)
            self.assertTrue(client.poll(timeout=1).pressed)
            event = client.poll(timeout=4)
            self.assertEqual(event.device_id, device.device_id)
            self.assertFalse(event.pressed)
            self.assertEqual(client.list_devices(), [])

    def test_slow_consumer_does_not_block_healthy_consumer(self):
        # Burst traffic must not delay delivery to a healthy consumer.
        with (
            Client(port=self.port) as slow,
            Client(port=self.port) as fast,
            Provider(port=self.port, timeout=10) as provider,
        ):
            slow._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
            slow.subscribe(MOTION)
            fast.subscribe(MOTION)
            device = provider.register_device("Example", "Device")
            stop = threading.Event()
            marker = threading.Event()
            errors = []

            def drain():
                while not stop.is_set():
                    try:
                        event = fast.poll(timeout=0.05)
                        if isinstance(event, MotionEvent) and event.tx == 4242:
                            marker.set()
                    except socket.timeout:
                        pass
                    except Exception as exc:
                        errors.append(exc)
                        return

            worker = threading.Thread(target=drain)
            worker.start()
            try:
                body = struct.pack(">IQ6i", device.device_id, 1, 123, 0, 0, 0, 0, 0)
                packet = HEADER.pack(b"O3DH", VERSION_MAJOR, VERSION_MINOR, 16, len(body), 0) + body
                provider._socket.sendall(packet * 50000)
                provider.publish_motion(device, 4242, 0, 0, 0, 0, 0)
                provider.ping()
                self.assertTrue(marker.wait(2), errors)
                self.assertFalse(errors)
            finally:
                stop.set()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
