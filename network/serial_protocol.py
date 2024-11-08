# network/serial_protocol.py

import asyncio
import re
import logging
from data.blink_manager import BlinkManager  # Adjust the import based on your project structure

class SerialProtocol(asyncio.Protocol):
    def __init__(self, blink_manager, LED_COUNT, stripall):
        super().__init__()
        self.transport = None
        self.buffer = ''
        self.blink_manager = blink_manager
        self.LED_COUNT = LED_COUNT
        self.stripall = stripall
        self.lock = asyncio.Lock()

        self.COMMAND_START = '#'
        self.COMMAND_END = '#'
        self.STOP_COMMAND = 'STOP'
        self.DETECTED_PREFIX = 'DETECTED:'  # Prefix for detection messages
        self.ACK_FORMAT = '#{}+#\n'
        self.BUFFER_MAX_SIZE = 4096  # Adjust based on expected usage
        self.pattern = re.compile(r'#(.*?)#')  # Pattern to extract messages between '#'

    def connection_made(self, transport):
        """
        Called when a serial connection is made.
        """
        self.transport = transport
        logging.info('Serial connection opened')

    def data_received(self, data):
        """
        Called when data is received from the serial port.
        """
        message = data.decode(errors='ignore')
        self.buffer += message
        asyncio.create_task(self.process_buffer())

    def connection_lost(self, exc):
        """
        Called when the serial connection is lost.
        """
        logging.info('Serial port closed')

    async def process_buffer(self):
        """
        Processes the buffered serial data to extract and handle commands.
        """
        async with self.lock:
            matches = list(self.pattern.finditer(self.buffer))
            if matches:
                for match in matches:
                    full_command = match.group(0)
                    command_content = match.group(1).strip()
                    logging.info(f"Processing command: {full_command}")

                    # Handle DETECTED commands
                    if command_content.startswith(self.DETECTED_PREFIX):
                        detected_led_str = command_content[len(self.DETECTED_PREFIX):].strip()
                        try:
                            detected_led = int(detected_led_str)
                            logging.info(f"Received detection confirmation for LED {detected_led}")

                            # Retrieve active block LEDs
                            active_block_leds = set()
                            if self.blink_manager.mode == 'block' and self.blink_manager.current_block:
                                active_block_leds = set(self.blink_manager.current_block.leds)

                            if detected_led in active_block_leds:
                                # Correct or expected LED detected
                                await self.blink_manager.handle_detection(detected_led)
                                acknowledgment_content = f"CORRECT:{detected_led}"
                                logging.info(f"LED {detected_led} is correct.")
                            else:
                                # Incorrect or unexpected LED detected
                                await self.blink_manager.handle_incorrect_detection(detected_led)
                                acknowledgment_content = f"FALSE:{detected_led}"
                                logging.info(f"LED {detected_led} is incorrect.")

                            # Send acknowledgment
                            acknowledgment = self.ACK_FORMAT.format(acknowledgment_content)
                            self.transport.write(acknowledgment.encode('utf-8'))
                        except ValueError:
                            logging.error(f"Invalid detected LED number: {detected_led_str}")
                            acknowledgment = self.ACK_FORMAT.format("INVALID_DETECTION")
                            self.transport.write(acknowledgment.encode('utf-8'))
                        continue  # Move to next match

                    # Process STOP command
                    if command_content.upper() == self.STOP_COMMAND:
                        await self.blink_manager.stop_blinking()
                        acknowledgment = self.ACK_FORMAT.format(self.STOP_COMMAND)
                        self.transport.write(acknowledgment.encode('utf-8'))
                        logging.info("Processed STOP command.")
                        continue  # Move to next match

                    # Handle LED commands (Single or Block)
                    led_pins = [pin.strip() for pin in command_content.split(',')]
                    led_pins_int = []
                    for pin in led_pins:
                        try:
                            led_pin = int(pin)
                            led_pins_int.append(led_pin)
                        except ValueError:
                            logging.error(f"Invalid LED number received: {pin}")

                    if led_pins_int:
                        if len(led_pins_int) > 1:
                            # It's a BLOCK
                            await self.blink_manager.add_block(led_pins_int, {})
                            acknowledgment = self.ACK_FORMAT.format(','.join(map(str, led_pins_int)))
                            self.transport.write(acknowledgment.encode('utf-8'))
                            logging.info(f"Processed LED block command: {led_pins_int}")
                        else:
                            # It's a single blink
                            await self.blink_manager.set_single_mode(led_pins_int[0])
                            acknowledgment = self.ACK_FORMAT.format(','.join(map(str, led_pins_int)))
                            self.transport.write(acknowledgment.encode('utf-8'))
                            logging.info(f"Processed LED single command: {led_pins_int[0]}")
                    else:
                        logging.warning("No valid LED numbers found in the command.")

                # Remove processed commands from buffer
                last_match_end = matches[-1].end()
                self.buffer = self.buffer[last_match_end:]
                logging.debug(f"Buffer after processing: {self.buffer}")
            else:
                if len(self.buffer) > self.BUFFER_MAX_SIZE:
                    logging.warning("Buffer overflow. Clearing buffer.")
                    self.buffer = ""
                return  # Wait for more data

    async def send_command(self, message):
        """
        Sends a command/message over the serial connection.

        :param message: The message string to send.
        """
        if self.transport:
            self.transport.write(message.encode('utf-8'))
            logging.debug(f"SerialProtocol: Sent message: {message.strip()}")
        else:
            logging.error("SerialProtocol: Transport is not available. Cannot send message.")
