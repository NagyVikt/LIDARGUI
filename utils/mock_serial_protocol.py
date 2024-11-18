# utils/mock_serial_protocol.py

class SerialProtocol:
    def __init__(self, blink_manager, LED_COUNT, stripall):
        self.blink_manager = blink_manager
        self.LED_COUNT = LED_COUNT
        self.stripall = stripall
        self.transport = self.MockTransport()

    class MockTransport:
        def write(self, data):
            print(f"Mock serial write: {data}")

        def close(self):
            print("Mock serial transport closed.")
