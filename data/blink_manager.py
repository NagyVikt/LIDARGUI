import asyncio
import time
import logging
from config.config import WINDOWS
import aiohttp

if WINDOWS:
    pass
else:
    from rpi_ws281x import Color

from collections import defaultdict


class Block:
    def __init__(self, led_sequence):
        """
        Initialize the Block with a sequence of LEDs.

        :param led_sequence: List of dictionaries with 'shelf_id' and 'led_id'.
        """
        self.led_sequence = led_sequence
        self.leds = []  # List of adjusted LED numbers
        self.current_index = 0
        self.lock = asyncio.Lock()
        self.green_counts = defaultdict(int)  # Tracks Green state counts per LED

    async def initialize_block(self, blink_manager, color_green=(0, 255, 0)):
        """
        Initialize the block by setting the first LED to green.
        Subsequent LEDs are managed without setting any to blue.

        :param blink_manager: Instance of BlinkManager to control LEDs.
        :param color_green: Tuple representing the green color.
        """
        for idx, led_info in enumerate(self.led_sequence):
            shelf_id = led_info['shelf_id']
            led_id = int(led_info['led_id'])
            controlled_value = blink_manager.get_controlled_value(shelf_id)
            # Adjust LED based on shelf ID
            adjusted_led = led_id + controlled_value
            self.leds.append(adjusted_led)

            if idx == self.current_index:
                # First LED: Set to Green
                self.green_counts[adjusted_led] += 1
                color = color_green
                logging.info(f"Shelf {shelf_id} LED {adjusted_led} set to Green.")
            else:
                # All other LEDs: Set to Off
                color = (0, 0, 0)
                logging.info(f"Shelf {shelf_id} LED {adjusted_led} set to Off.")

            await blink_manager.set_led_color(adjusted_led, color)
            await self.update_led_color(adjusted_led, blink_manager)  # Ensure color consistency
            
            if idx == self.current_index:
                await blink_manager.send_active_led(adjusted_led)  # Send active LED
                logging.info(f"SENT CURRENT ACTIVE LED TO JETSON: {adjusted_led}")


        logging.info(f"Added new block with LEDs: {self.leds}")

    
    async def handle_detection(self, detected_led, blink_manager):
        """
        Handle the detection of a specific LED within the block.

        :param detected_led: The LED number that was detected.
        :param blink_manager: Instance of BlinkManager to control LEDs.
        """
        async with self.lock:
            if self.current_index >= len(self.leds):
                logging.warning("All LEDs in the block have already been processed.")
                return

            expected_led = self.leds[self.current_index]

            if detected_led == expected_led:
                # Correct detection
                logging.info(f"LED {detected_led} correctly detected.")

                # Turn off the detected LED
                await blink_manager.set_led_color(detected_led, (0, 0, 0))  # Off
                shelf_id = blink_manager.get_shelf_id(detected_led)
                logging.info(f"Shelf {shelf_id} LED {detected_led} turned Off.")

                # Decrement the Green count
                if self.green_counts[detected_led] > 0:
                    self.green_counts[detected_led] -= 1

                # Move to the next LED in the sequence
                self.current_index += 1

                if self.current_index < len(self.leds):
                    # Set the next LED to Green
                    current_led = self.leds[self.current_index]
                    self.green_counts[current_led] += 1
                    await blink_manager.set_led_color(current_led, (0, 255, 0))  # Green
                    shelf_id = blink_manager.get_shelf_id(current_led)
                    await blink_manager.send_active_led(current_led)  # Send active LED
                    logging.info(f"SENT CURRENT ACTIVE LED TO JETSON: {current_led}")
                    logging.info(f"Shelf {shelf_id} LED {current_led} set to Green.")
                    
                else:
                    # Block processing complete
                    blink_manager.mode = None
                    logging.info("Block mode completed.")
                    await blink_manager.handle_block_completion()
                    blink_manager.current_block = None  # Set this after calling handle_block_completion
            else:
                # Any detection not equal to expected_led is incorrect
                if detected_led in self.leds:
                    logging.info(
                        f"Incorrect LED {detected_led} detected. Only LED {expected_led} is currently active."
                    )
                else:
                    logging.info(
                        f"LED {detected_led} is not part of the current block or already handled."
                    )
                # Schedule the incorrect detection handling without awaiting to prevent blocking
                asyncio.create_task(blink_manager.handle_incorrect_detection(detected_led))

    
    
    
    def determine_color(self, led_pin):
        """
        Determine the color of the LED based on green counts.

        :param led_pin: The LED pin number.
        :return: A tuple representing the color.
        """
        if self.green_counts[led_pin] > 0:
            return (0, 255, 0)  # Green
        else:
            return (0, 0, 0)    # Off

    async def update_led_color(self, led_pin, blink_manager):
        """
        Update the color of an LED based on current counts.

        :param led_pin: The LED pin number.
        :param blink_manager: Instance of BlinkManager to control LEDs.
        """
        color = self.determine_color(led_pin)
        await blink_manager.set_led_color(led_pin, color)
        shelf_id = blink_manager.get_shelf_id(led_pin)
        color_name = "Green" if color == (0, 255, 0) else "Off"
        logging.info(f"Shelf {shelf_id} LED {led_pin} updated to {color_name}.")


class BlinkManager:
    def __init__(self, stripall, LED_COUNT, shelf_led_count,serial_protocol=None, timeout=10):
        self.stripall = stripall
        self.LED_COUNT = LED_COUNT  # Number of LEDs per shelf
        self.shelf_led_count = shelf_led_count  # Total number of LEDs per shelf
        self.blocks = []  # List to keep track of all active blocks

        self.active_led_pins = {}  # Dictionary to track LEDs and their last update time
        self.blink_task = None
        self.blink_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self.timeout = timeout

        self.incorrect_leds = {}  # key: led_pin, value: asyncio.Task
        self.incorrect_led_last_detect_time = {}  # key: led_pin, value: last_detection_time

        # Mode tracking
        self.mode = None  # Can be 'single' or 'block'
        self.current_block = None  # To track the current block being processed

        # Store controlled values per shelf
        self.controlled_values = {}  # key: shelf_id, value: controlled_value

        # Mapping from led_pin to shelf_id for logging
        self.led_to_shelf = {}  # Initialize an empty dictionary
        self.serial_protocol = serial_protocol  # Reference to SerialProtocol


    async def send_active_led(self, led_pin):
        """
        Sends the currently active LED to the Jetson via serial.
        
        :param led_pin: The LED pin number to send.
        """
        if self.serial_protocol:
            message = f"#{led_pin}#\n"
            await self.serial_protocol.send_command(message)
            logging.info(f"Sent active LED to Jetson: {message.strip()}")
        else:
            logging.error("Serial protocol is not initialized. Cannot send active LED.")


    def get_controlled_value(self, shelf_id):
        """
        Return the controlled value for the given shelf_id.
        """
        return self.controlled_values.get(shelf_id, 0)

    def get_shelf_id(self, led_pin):
        """
        Retrieve the shelf_id for a given led_pin.

        :param led_pin: The LED pin number.
        :return: The shelf_id as a string.
        """
        return self.led_to_shelf.get(led_pin, "Unknown")

    async def add_block(self, led_sequence, controlled_values, color_green=(0, 255, 0)):
        """
        Adds a new block with the given led_sequence and controlled_values.

        :param led_sequence: List of dictionaries with 'shelf_id' and 'led_id'.
        :param controlled_values: Dictionary of controlled values per shelf.
        """
        # Store controlled values
        self.controlled_values = controlled_values

        # Map led_pin to shelf_id
        for led_info in led_sequence:
            shelf_id = led_info['shelf_id']
            led_id = int(led_info['led_id'])
            controlled_value = self.get_controlled_value(shelf_id)
            adjusted_led = led_id + controlled_value
            self.led_to_shelf[adjusted_led] = shelf_id

        # Initialize and add the new block with the ordered LED sequence
        block = Block(led_sequence)
        await block.initialize_block(self, color_green)

        async with self.lock:
            self.blocks.append(block)
            self.mode = 'block'
            self.current_block = block
        logging.info(f"Added new block with LEDs: {block.leds}")

    async def handle_block_completion(self):
        logging.info("handle_block_completion: Starting")
        try:
            # Get the list of shelves involved in the current block
            shelves = set(led_info['shelf_id'] for led_info in self.current_block.led_sequence)
            leds_to_blink = []

            for shelf_id in shelves:
                controlled_value = self.get_controlled_value(shelf_id)
                if shelf_id == '1':
                    # For Shelf 1, LEDs 1 to 132
                    leds = list(range(1, 133))
                elif shelf_id == '2':
                    # For Shelf 2, LEDs 1+controlled_value to 132+controlled_value
                    leds = [led + controlled_value for led in range(1, 133)]
                else:
                    logging.error(f"Unknown shelf_id: {shelf_id}. Cannot handle block completion.")
                    continue
                leds_to_blink.extend(leds)

            # Remove duplicates from leds_to_blink
            leds_to_blink = list(set(leds_to_blink))

            # Blink the LEDs for 3 cycles (on and off)
            for cycle in range(3):
                logging.info(f"handle_block_completion: Blinking cycle {cycle + 1}/3")
                await self.set_specific_leds_color(leds_to_blink, (0, 255, 0))  # Green color
                await asyncio.sleep(0.5)
                await self.turn_off_specific_leds(leds_to_blink)
                await asyncio.sleep(0.5)

            # Reset program state to default
            logging.info("handle_block_completion: Resetting program state to default")
            await self.turn_off_all_leds()

            # Notify connected clients
            logging.info("handle_block_completion: Notifying clients")
            await self.notify_clients_block_completed()
            logging.info("handle_block_completion: Completed")
        except Exception as e:
            logging.error(f"Exception in handle_block_completion: {e}")

    async def set_specific_leds_color(self, leds, color):
        """
        Sets specific LEDs to the specified color.
        """
        try:
            strip_updates = {}

            # Build updates without locks
            for led_pin in leds:
                if led_pin < 1 or led_pin > self.LED_COUNT * len(self.stripall):
                    logging.error(f"LED pin {led_pin} is out of range.")
                    continue

                strip_index = 0 if led_pin <= self.LED_COUNT else 1
                adjusted_led = led_pin - 1 if strip_index == 0 else led_pin - self.LED_COUNT - 1
                strip = self.stripall[strip_index]

                logging.debug(
                    f"Setting LED {led_pin} (adjusted index {adjusted_led}) on strip {strip_index} to color {color}"
                )

                if strip not in strip_updates:
                    strip_updates[strip] = []
                strip_updates[strip].append((adjusted_led, Color(*color)))

            # Apply updates without locks
            for strip, updates in strip_updates.items():
                for idx, color_value in updates:
                    strip.setPixelColor(idx, color_value)

            # Update the hardware without locks
            update_tasks = []
            for strip in strip_updates.keys():
                update_tasks.append(
                    asyncio.get_event_loop().run_in_executor(None, strip.show)
                )
            await asyncio.gather(*update_tasks)

        except Exception as e:
            logging.error(f"Exception in set_specific_leds_color: {e}")

    async def turn_off_specific_leds(self, leds):
        """
        Turns off specific LEDs.
        """
        await self.set_specific_leds_color(leds, (0, 0, 0))

    async def notify_clients_block_completed(self):
        logging.info("notify_clients_block_completed: Sending message to clients")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('http://localhost:8080/block_completed') as response:
                    if response.status == 200:
                        logging.info("Successfully notified led_controller.py")
                    else:
                        logging.error(f"Failed to notify led_controller.py, status code {response.status}")
        except Exception as e:
            logging.error(f"Exception in notify_clients_block_completed: {e}")

    async def set_all_leds_color(self, color):
        """
        Sets all LEDs to the specified color.
        """
        try:
            # Set the color for all LEDs on each strip
            for strip_index, strip in enumerate(self.stripall):
                for i in range(self.LED_COUNT):
                    strip.setPixelColor(i, Color(*color))

            # Update the hardware without locks
            update_tasks = []
            for strip in self.stripall:
                update_tasks.append(
                    asyncio.get_event_loop().run_in_executor(None, strip.show)
                )
            await asyncio.gather(*update_tasks)

        except Exception as e:
            logging.error(f"Exception in set_all_leds_color: {e}")

    async def turn_off_all_leds_no_clear(self):
        """
        Turns off all LEDs without clearing modes or blocks.
        """
        # Build the updates without holding the lock
        strip_updates = []
        for strip in self.stripall:
            updates = []
            for i in range(self.LED_COUNT):
                updates.append((i, Color(0, 0, 0)))
            strip_updates.append((strip, updates))

        # Apply updates while holding the lock
        async with self.lock:
            for strip, updates in strip_updates:
                for idx, color_value in updates:
                    strip.setPixelColor(idx, color_value)

        # Now, update the hardware without holding the lock
        for strip, _ in strip_updates:
            await asyncio.get_event_loop().run_in_executor(None, strip.show)

    async def handle_detection(self, detected_led):
        """
        Handles the detection of a LED based on the current mode.
        """
        async with self.lock:
            if self.mode == 'single':
                await self.confirm_single_detection(detected_led)
            elif self.mode == 'block':
                if self.current_block:
                    await self.current_block.handle_detection(detected_led, self)
            else:
                # Handle detections outside of modes if necessary
                for block in self.blocks:
                    if detected_led in block.leds:
                        await block.handle_detection(detected_led, self)
                        break
                else:
                    logging.info(f"Detected LED {detected_led} is not part of any active block.")

    async def confirm_single_detection(self, led_pin):
        """
        Confirms detection in single mode.

        :param led_pin: The detected LED number.
        """
        if led_pin in self.active_led_pins:
            await self.set_led_color(led_pin, (0, 0, 0))
            del self.active_led_pins[led_pin]
            self.mode = None
            logging.info(f"Single mode completed for LED {led_pin}")

    async def set_led_color(self, led_pin, color):
        """
        Sets the color of a specific LED.

        :param led_pin: The LED pin number.
        :param color: The color tuple to set.
        """
        try:
            led_pin = int(led_pin)
        except ValueError:
            logging.error(f"Invalid led_pin value: {led_pin}. It must be an integer.")
            return

        if led_pin < 1 or led_pin > self.LED_COUNT * len(self.stripall):
            logging.error(f"LED pin {led_pin} is out of range.")
            return

        strip_index = 0 if led_pin <= self.LED_COUNT else 1
        adjusted_led = led_pin - 1 if strip_index == 0 else led_pin - self.LED_COUNT - 1
        strip = self.stripall[strip_index]
        try:
            strip.setPixelColor(adjusted_led, Color(*color))
            await asyncio.get_event_loop().run_in_executor(None, strip.show)
        except Exception as e:
            logging.error(f"Failed to set color for LED {led_pin}: {e}")

    async def turn_off_led(self, led_pin):
        """
        Turns off a specific LED.

        :param led_pin: The LED pin number.
        """
        await self.set_led_color(led_pin, (0, 0, 0))

    async def turn_off_all_leds(self):
        """
        Turns off all active LEDs and clears all blocks.
        """
        try:
            # Turn off all LEDs
            await self.set_all_leds_color((0, 0, 0))
            logging.debug("All LEDs have been turned off.")

            # Clear internal state
            self.active_led_pins.clear()
            logging.debug("Cleared self.active_led_pins.")
            self.blocks.clear()
            logging.debug("Cleared self.blocks.")
            self.mode = None
            logging.debug("Set self.mode to None.")
            self.current_block = None
            logging.debug("Set self.current_block to None.")
            self.controlled_values.clear()
            logging.debug("Cleared controlled values.")

            # Cancel any incorrect blink tasks
            for task in self.incorrect_leds.values():
                task.cancel()
            self.incorrect_leds.clear()
            self.incorrect_led_last_detect_time.clear()
            logging.debug("Cleared incorrect LED tasks and last detection times.")

            logging.info("All LEDs turned off and blocks cleared.")
        except Exception as e:
            logging.error(f"Exception in turn_off_all_leds: {e}")

    async def handle_incorrect_detection(self, led_pin):
        """
        Handles incorrect LED detections by blinking red for 1 second per detection.
        If the same LED is detected again within this period, the blink timer resets.

        :param led_pin: The incorrect LED number.
        """
        async with self.lock:
            current_time = time.time()
            self.incorrect_led_last_detect_time[led_pin] = current_time

            if led_pin not in self.incorrect_leds:
                # Start a new blink task for this LED
                self.incorrect_leds[led_pin] = asyncio.create_task(self._incorrect_led_behavior(led_pin))
                logging.info(f"Started handling incorrect LED {led_pin}")
            else:
                # Task already exists; it will pick up the new detection time
                logging.info(f"LED {led_pin} is already being handled. Updated last detection time.")

    async def _incorrect_led_behavior(self, led_pin):
        """
        Manages the blinking behavior for an incorrect LED.
        Blinks red every 0.5 seconds as long as detections occur within 1-second intervals.

        :param led_pin: The incorrect LED number.
        """
        try:
           
                # Blink red on
                await self.set_led_color(led_pin, (255, 0, 0))
 
                await asyncio.sleep(0.3)

                # Blink red off
                await self.set_led_color(led_pin, (0, 0, 0))
 

        except asyncio.CancelledError:
            logging.info(f"Blink task for LED {led_pin} was cancelled.")
        finally:
            # Ensure the LED is turned off
            await self.turn_off_led(led_pin)
            async with self.lock:
                # Remove the task and last detection time
                self.incorrect_leds.pop(led_pin, None)
                self.incorrect_led_last_detect_time.pop(led_pin, None)
            logging.info(f"Stopped handling incorrect LED {led_pin}")

    async def set_single_mode(self, led_pin, color_green=(0, 255, 0)):
        """
        Sets the system to single mode for a specific LED.

        :param led_pin: The LED number to set to Green.
        :param color_green: Color tuple for Green.
        """
        async with self.lock:
            self.mode = 'single'
            self.active_led_pins.clear()
            self.active_led_pins[led_pin] = time.time()
            await self.set_led_color(led_pin, color_green)
            logging.info(f"Single mode activated for LED {led_pin} with color {color_green}")

    async def set_active_leds(self, new_leds):
        """
        Sets new active LEDs to blink. Always restarts the blinking task.

        :param new_leds: List of LED numbers to activate.
        """
        # Stop the previous blinking task
        if self.blink_task and not self.blink_task.done():
            self.blink_event.set()
            self.blink_task.cancel()
            try:
                await self.blink_task
            except asyncio.CancelledError:
                logging.info("Blink task was cancelled.")
            except Exception as e:
                logging.error(f"Error in blinking task: {e}")

        # Update the active LEDs
        async with self.lock:
            self.active_led_pins.clear()
            current_time = time.time()
            for led_pin in new_leds:
                self.active_led_pins[led_pin] = current_time
                logging.info(f"Added LED {led_pin} to active blinking list.")

        # Start a new blinking task
        self.blink_event = asyncio.Event()  # Reset the event
        self.blink_task = asyncio.create_task(self.blink_leds())
        logging.info(f"Started blinking LEDs: {new_leds}")

    async def blink_leds(self):
        """
        Blinks all active LEDs red until they are detected or timeout occurs.
        """
        try:
            while True:
                if self.blink_event.is_set():
                    break  # Exit if the event is set

                try:
                    async with self.lock:
                        current_time = time.time()
                        leds_to_remove = []
                        strip_updates = {}

                        # Handle active blinking LEDs
                        for led_pin, last_update in list(self.active_led_pins.items()):
                            if current_time - last_update > self.timeout:
                                leds_to_remove.append(led_pin)
                                continue

                            if led_pin < 1 or led_pin > self.LED_COUNT * len(self.stripall):
                                logging.error(f"LED pin {led_pin} is out of range.")
                                continue

                            # Determine which strip the LED belongs to
                            if led_pin <= self.LED_COUNT:
                                strip = self.stripall[0]
                                adjusted_led = led_pin - 1
                            else:
                                strip = self.stripall[1]
                                adjusted_led = led_pin - self.LED_COUNT - 1

                            if strip not in strip_updates:
                                strip_updates[strip] = []
                            strip_updates[strip].append((adjusted_led, Color(255, 0, 0)))  # Red color

                        # Remove LEDs that have timed out
                        for led_pin in leds_to_remove:
                            del self.active_led_pins[led_pin]
                            await self.turn_off_led(led_pin)
                            logging.info(f"LED {led_pin} turned off due to timeout.")

                        # If no more LEDs to blink and no active blocks, exit the task
                        if not self.active_led_pins and not self.blocks and self.mode != 'block':
                            logging.info("No active LEDs or blocks left to blink. Stopping blink task.")
                            break

                        # Update all strips at once
                        for strip, updates in strip_updates.items():
                            for idx, color in updates:
                                strip.setPixelColor(idx, color)
                            await asyncio.get_event_loop().run_in_executor(None, strip.show)

                except Exception as e:
                    logging.error(f"Error in blink_leds loop: {e}")

                await asyncio.sleep(0.5)

                if self.blink_event.is_set():
                    break  # Exit if the event is set

                # Turn off all active LEDs
                async with self.lock:
                    strip_updates = {}
                    for led_pin in self.active_led_pins.keys():
                        if led_pin <= self.LED_COUNT:
                            strip = self.stripall[0]
                            adjusted_led = led_pin - 1
                        else:
                            strip = self.stripall[1]
                            adjusted_led = led_pin - self.LED_COUNT - 1

                        if strip not in strip_updates:
                            strip_updates[strip] = []
                        strip_updates[strip].append((adjusted_led, Color(0, 0, 0)))  # Turn off

                    # Update all strips at once
                    for strip, updates in strip_updates.items():
                        for idx, color in updates:
                            strip.setPixelColor(idx, color)
                        await asyncio.get_event_loop().run_in_executor(None, strip.show)

                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logging.info("Blink task was cancelled.")
        finally:
            # Ensure all LEDs are turned off when the task ends
            await self.turn_off_all_leds()
            logging.info("Blink task has been cleaned up and all LEDs are turned off.")

    async def stop_blinking(self):
        """
        Stops the blinking task and turns off all LEDs.
        """
        if self.blink_task and not self.blink_task.done():
            self.blink_event.set()
            self.blink_task.cancel()
            try:
                await self.blink_task
            except asyncio.CancelledError:
                logging.info("Blink task was cancelled.")
            except Exception as e:
                logging.error(f"Error in blinking task: {e}")
        await self.turn_off_all_leds()
        logging.info("Stopped blinking and turned off all LEDs.")
