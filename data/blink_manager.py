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
    def __init__(self, led_sequence, cooldown=1, per_led_cooldown=0.5):
        self.led_sequence = led_sequence
        self.leds = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        self.green_counts = defaultdict(int)
        self.last_correct_detection_time = 0
        self.processed_leds = defaultdict(float)
        self.cooldown = cooldown
        self.per_led_cooldown = per_led_cooldown

        # Add a set to track LEDs to ignore (neighbors and cooldown LEDs)
        self.ignored_leds = set()

    async def initialize_block(self, blink_manager, color_green=(0, 255, 0)):
        for idx, led_info in enumerate(self.led_sequence):
            shelf_id = led_info['shelf_id']
            led_id = int(led_info['led_id'])
            controlled_value = blink_manager.get_controlled_value(shelf_id)
            adjusted_led = led_id + controlled_value
            self.leds.append(adjusted_led)

            if idx == self.current_index:
                self.green_counts[adjusted_led] += 1
                color = color_green
                logging.info(f"Shelf {shelf_id} LED {adjusted_led} set to Green.")
            else:
                color = (0, 0, 0)
                logging.info(f"Shelf {shelf_id} LED {adjusted_led} set to Off.")

            await self.update_led_color(adjusted_led, blink_manager)

            if idx == self.current_index:
                await blink_manager.send_active_led(adjusted_led)
                logging.info(f"SENT CURRENT ACTIVE LED TO JETSON: {adjusted_led}")

        logging.info(f"Added new block with LEDs: {self.leds}")

    async def handle_detection(self, detected_led, blink_manager):
        async with self.lock:
            current_time = time.time()
            expected_led = self.leds[self.current_index] if self.current_index < len(self.leds) else None

            logging.debug(f"Handling detection for LED {detected_led}. Current index: {self.current_index}, Expected LED: {expected_led}")

            if self.current_index >= len(self.leds):
                logging.warning("All LEDs in the block have already been processed.")
                return

            # Check if the detected_led has already been processed within the per-LED cooldown
            last_processed_time = self.processed_leds.get(detected_led, 0)
            time_since_last = current_time - last_processed_time

            if time_since_last < self.per_led_cooldown:
                logging.info(
                    f"LED {detected_led} detected again within cooldown ({time_since_last:.3f} seconds). Ignoring."
                )
                return  # Skip processing this detection

            if detected_led == expected_led:
                # Handle correct detection
                time_since_last_block = current_time - self.last_correct_detection_time
                if time_since_last_block < self.cooldown:
                    logging.info(
                        f"Correct detection {detected_led} skipped due to block cooldown. "
                        f"{time_since_last_block:.2f} seconds since last correct detection."
                    )
                    return

                self.processed_leds[detected_led] = current_time
                self.last_correct_detection_time = current_time
                logging.info(f"LED {detected_led} correctly detected.")

                await blink_manager.set_led_color(detected_led, (0, 0, 0))  # Turn off the LED
                shelf_id = blink_manager.get_shelf_id(detected_led)
                logging.info(f"Shelf {shelf_id} LED {detected_led} turned Off.")

                if self.green_counts[detected_led] > 0:
                    self.green_counts[detected_led] -= 1

                # Add neighboring LEDs to ignored list with a cooldown
                neighbors = [detected_led - 1, detected_led + 1]
                self.ignored_leds.update(neighbors)
                # Store the time when neighbors were added to ignore list
                for neighbor in neighbors:
                    self.processed_leds[neighbor] = current_time

                # **Cleanup incorrect detection state for the detected LED**
                if detected_led in blink_manager.incorrect_leds:
                    # Cancel the incorrect blinking task for this LED
                    blink_manager.incorrect_leds[detected_led].cancel()
                    blink_manager.incorrect_leds.pop(detected_led, None)
                    blink_manager.incorrect_led_last_detect_time.pop(detected_led, None)
                    logging.info(f"Cleared incorrect detection state for LED {detected_led}")

                # Move to the next LED
                self.current_index += 1
                logging.debug(f"Incremented current_index to {self.current_index}.")

                if self.current_index < len(self.leds):
                    current_led = self.leds[self.current_index]

                    # **Cleanup incorrect detection state for the new expected LED**
                    if current_led in blink_manager.incorrect_leds:
                        blink_manager.incorrect_leds[current_led].cancel()
                        blink_manager.incorrect_leds.pop(current_led, None)
                        blink_manager.incorrect_led_last_detect_time.pop(current_led, None)
                        logging.info(f"Cleared incorrect detection state for LED {current_led}")

                    self.green_counts[current_led] += 1
                    await blink_manager.set_led_color(current_led, (0, 255, 0))  # Set to Green
                    shelf_id = blink_manager.get_shelf_id(current_led)
                    await blink_manager.send_active_led(current_led)
                    logging.info(f"SENT CURRENT ACTIVE LED TO JETSON: {current_led}")
                    logging.info(f"Shelf {shelf_id} LED {current_led} set to Green.")
                else:
                    blink_manager.mode = None
                    logging.info("Block mode completed.")
                    await blink_manager.handle_block_completion()
                    blink_manager.current_block = None
            else:
                # Handle incorrect detection
                # Check if detected_led is a neighbor of expected_led
                if detected_led in self.ignored_leds:
                    # Ignore the detection for neighboring LEDs
                    logging.info(f"Detected neighboring LED {detected_led} is ignored during cooldown.")
                    return
                if detected_led in self.leds:
                    logging.info(
                        f"Incorrect LED {detected_led} detected. Only LED {expected_led} is currently active."
                    )
                else:
                    logging.info(
                        f"LED {detected_led} is not part of the current block or already handled."
                    )
                asyncio.create_task(blink_manager.handle_incorrect_detection(detected_led))

            # Cleanup processed_leds
            keys_to_remove = [led for led, timestamp in self.processed_leds.items()
                            if current_time - timestamp > 2]  # 2 seconds cooldown
            for led in keys_to_remove:
                self.processed_leds.pop(led, None)
                self.ignored_leds.discard(led)



    def determine_color(self, led_pin):
        if self.green_counts[led_pin] > 0:
            return (0, 255, 0)  # Green
        else:
            return (0, 0, 0)    # Off

    async def update_led_color(self, led_pin, blink_manager):
        color = self.determine_color(led_pin)
        await blink_manager.set_led_color(led_pin, color)
        shelf_id = blink_manager.get_shelf_id(led_pin)
        color_name = "Green" if color == (0, 255, 0) else "Off"
        logging.info(f"Shelf {shelf_id} LED {led_pin} updated to {color_name}.")





class BlinkManager:
    def __init__(self, stripall, LED_COUNT, shelf_led_count, serial_protocol=None, timeout=10, debounce_time=0.1):
        """
        Initialize the BlinkManager.

        :param stripall: List of LED strip instances.
        :param LED_COUNT: Number of LEDs per strip.
        :param shelf_led_count: Total number of LEDs per shelf.
        :param serial_protocol: Instance of SerialProtocol for communication.
        :param timeout: Timeout duration in seconds for blinking.
        :param debounce_time: Debounce time in seconds to ignore rapid detections.
        """
        self.stripall = stripall
        self.LED_COUNT = LED_COUNT
        self.shelf_led_count = shelf_led_count
        self.blocks = []
        self.active_led_pins = {}
        self.blink_task = None
        self.blink_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self.timeout = timeout
        self.incorrect_leds = {}
        self.incorrect_led_last_detect_time = {}
        self.mode = None
        self.current_block = None
        self.controlled_values = {}
        self.led_to_shelf = {}
        self.serial_protocol = serial_protocol
        self.debounce_time = debounce_time
        self.last_detection_time = defaultdict(float)

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

   
    def get_shelf_id(self, led_pin):
        return self.led_to_shelf.get(led_pin, "Unknown")

    async def add_block(self, led_sequence, controlled_values, color_green=(0, 255, 0)):
        async with self.lock:
            if self.mode == 'block':
                logging.warning("A block is already being processed. New block addition is skipped.")
                return

            self.controlled_values = controlled_values

            for led_info in led_sequence:
                shelf_id = led_info['shelf_id']
                led_id = int(led_info['led_id'])
                controlled_value = self.get_controlled_value(shelf_id)
                adjusted_led = led_id + controlled_value
                self.led_to_shelf[adjusted_led] = shelf_id

            block = Block(led_sequence, cooldown=1, per_led_cooldown=0.5)
            await block.initialize_block(self, color_green)

            self.blocks.append(block)
            self.mode = 'block'
            self.current_block = block
            logging.info(f"Added new block with LEDs: {block.leds}")

    async def handle_block_completion(self):
        logging.info("handle_block_completion: Starting")
        try:
            if not self.current_block:
                logging.warning("No current block to complete.")
                return

            shelves = set(led_info['shelf_id'] for led_info in self.current_block.led_sequence)
            leds_to_blink = []

            for shelf_id in shelves:
                controlled_value = self.get_controlled_value(shelf_id)
                if shelf_id == '1':
                    leds = list(range(1, self.LED_COUNT + 1))
                elif shelf_id == '2':
                    leds = [led + controlled_value for led in range(1, self.LED_COUNT + 1)]
                else:
                    logging.error(f"Unknown shelf_id: {shelf_id}. Cannot handle block completion.")
                    continue
                leds_to_blink.extend(leds)

            leds_to_blink = list(set(leds_to_blink))

            for cycle in range(3):
                logging.info(f"handle_block_completion: Blinking cycle {cycle + 1}/3")
                await self.set_specific_leds_color(leds_to_blink, (0, 255, 0))  # Green color
                await asyncio.sleep(0.5)
                await self.turn_off_specific_leds(leds_to_blink)
                await asyncio.sleep(0.5)

            logging.info("handle_block_completion: Resetting program state to default")
            await self.turn_off_all_leds()

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
        Implements a debounce mechanism to ignore rapid repeated detections.

        :param detected_led: The LED number that was detected.
        """
        try:
            detected_led = int(detected_led)
        except ValueError:
            logging.error(f"Invalid detected_led value: {detected_led}. It must be an integer.")
            return

        current_time = time.time()
        if current_time - self.last_detection_time[detected_led] < self.debounce_time:
            logging.info(f"Debounced detection for LED {detected_led}. Ignoring.")
            return  # Ignore the detection
        self.last_detection_time[detected_led] = current_time

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
            logging.debug(f"Set LED {led_pin} on strip {strip_index} to color {color}.")
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
        async with self.lock:
            current_time = time.time()
            # Check if the LED is ignored (neighboring LEDs with cooldown)
            if self.current_block and led_pin in self.current_block.ignored_leds:
                last_processed_time = self.current_block.processed_leds.get(led_pin, 0)
                if current_time - last_processed_time < 2:  # 2 seconds cooldown
                    logging.info(f"LED {led_pin} is ignored during cooldown.")
                    return

            # If the led_pin is the expected LED now, do not handle it as incorrect
            expected_led = self.current_block.leds[self.current_block.current_index] if self.current_block else None
            if led_pin == expected_led:
                logging.info(f"LED {led_pin} is now the expected LED. Not handling as incorrect.")
                return

            self.incorrect_led_last_detect_time[led_pin] = current_time

            if led_pin not in self.incorrect_leds:
                self.incorrect_leds[led_pin] = asyncio.create_task(self._incorrect_led_behavior(led_pin))
                logging.info(f"Started handling incorrect LED {led_pin}")
            else:
                logging.info(f"LED {led_pin} is already being handled. Updated last detection time.")

    async def _incorrect_led_behavior(self, led_pin):
        """
        Manages the blinking behavior for an incorrect LED.
        Blinks red every 0.3 seconds as long as detections occur within 1-second intervals.
        """
        try:
            while True:
                # Before blinking, check if the LED has become the expected LED
                expected_led = self.current_block.leds[self.current_block.current_index] if self.current_block else None
                if led_pin == expected_led:
                    logging.info(f"LED {led_pin} has become the expected LED. Stopping incorrect blinking.")
                    break  # Exit the blinking loop

                current_time = time.time()
                last_detect_time = self.incorrect_led_last_detect_time.get(led_pin, 0)

                # Blink red on
                await self.set_led_color(led_pin, (255, 0, 0))
                await asyncio.sleep(0.1)

                # Blink red off
                await self.set_led_color(led_pin, (0, 0, 0))
                await asyncio.sleep(0.1)

                # Check if a new detection has occurred within the last 1 second
                if current_time - last_detect_time > 0.1:
                    break  # Exit the blinking loop

        except asyncio.CancelledError:
            logging.info(f"Blink task for LED {led_pin} was cancelled.")
        finally:
            # Ensure the LED is correctly set after stopping incorrect blinking
            expected_led = self.current_block.leds[self.current_block.current_index] if self.current_block else None
            if led_pin != expected_led:
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
