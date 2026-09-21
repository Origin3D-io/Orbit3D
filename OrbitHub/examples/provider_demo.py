"""Hardware-free provider demonstration using only the public SDK."""

import argparse
import math
import time

from orbit3d_hub import Provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=43120)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--rate", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.rate <= 500 or args.seconds <= 0:
        parser.error("rate must be 1..500 and seconds must be positive")
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        try:
            with Provider(port=args.port) as provider:
                device = provider.register_device("Example", "Demo Controller", "demo-1", 2)
                print("Publishing Example/Demo Controller/demo-1", flush=True)
                next_button = time.monotonic() + 3
                while time.monotonic() < deadline:
                    now = time.monotonic()
                    provider.publish_motion(device, round(math.sin(now) * 250000), 0, 0, 0, 0, 0)
                    if now >= next_button:
                        # A quick click tests that the application preserves both edges.
                        provider.publish_button(device, 1, True)
                        provider.publish_button(device, 1, False)
                        next_button = now + 3
                    time.sleep(1 / args.rate)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Waiting for OrbitHub: {exc}", flush=True)
            time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
