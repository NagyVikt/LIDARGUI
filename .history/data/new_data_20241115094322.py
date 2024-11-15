import asyncio
import logging
import time
from collections import defaultdict
from rpi_ws281x import Color
import aiohttp

class Block:
    def __init__(self, led_sequence, cooldown=3, per_led_cooldown=0.5):
        self.led_sequence = led_sequence
        self.cooldown = cooldown
        self.per_led_cooldown = per_led_cooldown
        self.leds = []
        self.current_index = 0
        self.green_counts = defaultdict(int)
        self.processed_leds = {}
        self.ignored_leds = set()

    async def initialize_block(self, blink_manager, color_green=(0, 255, 0)):
        self.leds = []
        for led_info in self.led_sequence:
            shelf_id = led_info['shelf_id']
            led_id = int(led_info['led_id'])
            controlled_value = blink_manager.get_controlled_value(shelf_id)
            adjusted_led = led_id + controlled_value
            self.leds.append(adjusted_led)
            blink_manager.led_to_shelf[adjusted_led] = shelf_id

        if self.leds:
            current_led = self.leds[0]
            self.green_counts[current_led] += 1
            await blink_manager.set_led_color(current_led, color_green)
            shelf_id = blink_manager.get_shelf_id(current_led)
            await blink_manager.send_active_led(current_led)
            logging.info(f"Shelf {shelf_id} LED {current_led} set to Green.")

    async def handle_detection(self, detected_led, blink_manager):
        expected_led = self.leds[self.current_index] if self.current_index < len(self.leds) else None
        current_time = time.time()

        if detected_led == expected_led:
            await blink_manager.set_led_color(detected_led, (0, 0, 0))  # Turn off
            logging.info(f"LED {detected_led} correctly detected and turned off.")

            if self.green_counts[detected_led] > 0:
                self.green_counts[detected_led] -= 1

            # Add neighboring LEDs to ignored list with a cooldown
            neighbors = [detected_led - 1, detected_led + 1]
            self.ignored_leds.update(neighbors)
            for neighbor in neighbors:
                self.processed_leds[neighbor] = current_time

            # Move to the next LED
            self.current_index += 1
            logging.debug(f"Incremented current_index to {self.current_index}.")

            if self.current_index < len(self.leds):
                current_led = self.leds[self.current_index]
                self.green_counts[current_led] += 1
                await blink_manager.set_led_color(current_led, (0, 255, 0))  # Green
                shelf_id = blink_manager.get_shelf_id(current_led)
                await blink_manager.send_active_led(current_led)
                logging.info(f"Shelf {shelf_id} LED {current_led} set to Green.")
            else:
                blink_manager.mode = None
                logging.info("Block mode completed.")
                await blink_manager.handle_block_completion()
                blink_manager.current_block = None
        else:
            # Handle incorrect detection
            if detected_led in self.ignored_leds:
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
        return (0, 255, 0) if self.green_counts[led_pin] > 0 else (0, 0, 0)

    async def update_led_color(self, led_pin, blink_manager):
        color = self.determine_color(led_pin)
        await blink_manager.set_led_color(led_pin, color)
        shelf_id = blink_manager.get_shelf_id(led_pin)
        color_name = "Green" if color == (0, 255, 0) else "Off"
        logging.info(f"Shelf {shelf_id} LED {led_pin} updated to {color_name}.")

class BlinkManager:
    def __init__(self, stripall, LED_COUNT, shelf_led_count, serial_protocol=None, timeout=10, debounce_time=0.1):
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
        if self.serial_protocol:
            message = f"#{led_pin}#\n"
            await self.serial_protocol.send_command(message)
            logging.info(f"Sent active LED to Jetson: {message.strip()}")
        else:
            logging.error("Serial protocol is not initialized. Cannot send active LED.")

    def get_controlled_value(self, shelf_id):
        return self.controlled_values.get(shelf_id, 0)

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

            block = Block(led_sequence, cooldown=3, per_led_cooldown=0.5)
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
        try:
            strip_updates = {}
            for led_pin in leds:
                strip_index, adjusted_led = self.get_strip_and_index(led_pin)
                strip = self.stripall[strip_index]
                if strip not in strip_updates:
                    strip_updates[strip] = []
                strip_updates[strip].append((adjusted_led, Color(*color)))

            for strip, updates in strip_updates.items():
                for idx, color_value in updates:
                    strip.setPixelColor(idx, color_value)
                await asyncio.get_event_loop().run_in_executor(None, strip.show)
        except Exception as e:
            logging.error(f"Exception in set_specific_leds_color: {e}")

    async def turn_off_specific_leds(self, leds):
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
        try:
            strip_updates = {}
            for strip in self.stripall:
                strip_updates[strip] = [(i, Color(*color)) for i in range(self.LED_COUNT)]

            for strip, updates in strip_updates.items():
                for idx, color_value in updates:
                    strip.setPixelColor(idx, color_value)
                await asyncio.get_event_loop().run_in_executor(None, strip.show)
        except Exception as e:
            logging.error(f"Exception in set_all_leds_color: {e}")

    async def turn_off_all_leds_no_clear(self):
        await self.set_all_leds_color((0, 0, 0))

    async def handle_detection(self, detected_led):
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

        if self.mode == 'single':
            await self.confirm_single_detection(detected_led)
        elif self.mode == 'block':
            if self.current_block:
                await self.current_block.handle_detection(detected_led, self)
        else:
            for block in self.blocks:
                if detected_led in block.leds:
                    await block.handle_detection(detected_led, self)
                    break
            else:
                logging.info(f"Detected LED {detected_led} is not part of any active block.")

    async def confirm_single_detection(self, led_pin):
        if led_pin in self.active_led_pins:
            await self.set_led_color(led_pin, (0, 0, 0))
            del self.active_led_pins[led_pin]
            self.mode = None
            logging.info(f"Single mode completed for LED {led_pin}")

    async def set_led_color(self, led_pin, color):
        try:
            led_pin = int(led_pin)
        except ValueError:
            logging.error(f"Invalid led_pin value: {led_pin}. It must be an integer.")
            return

        strip_index, adjusted_led = self.get_strip_and_index(led_pin)
        strip = self.stripall[strip_index]
        try:
            strip.setPixelColor(adjusted_led, Color(*color))
            await asyncio.get_event_loop().run_in_executor(None, strip.show)
            logging.debug(f"Set LED {led_pin} on strip {strip_index} to color {color}.")
        except Exception as e:
            logging.error(f"Failed to set color for LED {led_pin}: {e}")

    def get_strip_and_index(self, led_pin):
        if led_pin <= self.LED_COUNT:
            return 0, led_pin - 1
        else:
            return 1, led_pin - self.LED_COUNT - 1

    async def turn_off_led(self, led_pin):
        await self.set_led_color(led_pin, (0, 0, 0))

    async def turn_off_all_leds(self):
        try:
            await self.set_all_leds_color((0, 0, 0))
            logging.debug("All LEDs have been turned off.")

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

            for task in self.incorrect_leds.values():
                task.cancel()
            self.incorrect_leds.clear()
            self.incorrect_led_last_detect_time.clear()
            logging.debug("Cleared incorrect LED tasks and last detection times.")

            logging.info("All LEDs turned off and blocks cleared.")
        except Exception as e:
            logging.error(f"Exception in turn_off_all_leds: {e}")

    async def handle_incorrect_detection(self, led_pin):
        current_time = time.time()
        if self.current_block and led_pin in self.current_block.ignored_leds:
            last_processed_time = self.current_block.processed_leds.get(led_pin, 0)
            if current_time - last_processed_time < 2:
                logging.info(f"LED {led_pin} is ignored during cooldown.")
                return
        self.incorrect_led_last_detect_time[led_pin] = current_time

        if led_pin not in self.incorrect_leds:
            self.incorrect_leds[led_pin] = asyncio.create_task(self._incorrect_led_behavior(led_pin))
            logging.info(f"Started handling incorrect LED {led_pin}")
        else:
            logging.info(f"LED {led_pin} is already being handled. Updated last detection time.")

    async def _incorrect_led_behavior(self, led_pin):
        try:
            while True:
                current_time = time.time()
                last_detect_time = self.incorrect_led_last_detect_time.get(led_pin, 0)

                await self.set_led_color(led_pin, (255, 0, 0))
                await asyncio.sleep(0.3)

                await self.set_led_color(led_pin, (0, 0, 0))
                await asyncio.sleep(0.3)

                if current_time - last_detect_time > 1:
                    break
        except asyncio.CancelledError:
            logging.info(f"Blink task for LED {led_pin} was cancelled.")
        finally:
            await self.turn_off_led(led_pin)
            self.incorrect_leds.pop(led_pin, None)
            self.incorrect_led_last_detect_time.pop(led_pin, None)
            logging.info(f"Stopped handling incorrect LED {led_pin}")

    async def set_single_mode(self, led_pin, color_green=(0, 255, 0)):
        async with self.lock:
            self.mode = 'single'
            self.active_led_pins.clear()
            self.active_led_pins[led_pin] = time.time()
            await self.set_led_color(led_pin, color_green)
            logging.info(f"Single mode activated for LED {led_pin} with color {color_green}")

    async def set_active_leds(self, new_leds):
        if self.blink_task and not self.blink_task.done():
            self.blink_event.set()
            self.blink_task.cancel()
            try:
                await self.blink_task
            except asyncio.CancelledError:
                logging.info("Blink task was cancelled.")
            except Exception as e:
                logging.error(f"Error in blinking task: {e}")

        self.active_led_pins.clear()
        current_time = time.time()
        for led_pin in new_leds:
            self.active_led_pins[led_pin] = current_time
            logging.info(f"Added LED {led_pin} to active blinking list.")

        self.blink_event = asyncio.Event()
        self.blink_task = asyncio.create_task(self.blink_leds())
        logging.info(f"Started blinking LEDs: {new_leds}")

    async def blink_leds(self):
        next_tick = time.time()
        try:
            while not self.blink_event.is_set():
                await self.perform_blink()

                next_tick += 0.5
                sleep_duration = max(0, next_tick - time.time())
                await asyncio.sleep(sleep_duration)
        except asyncio.CancelledError:
            logging.info("Blink task was cancelled.")
        finally:
            await self.turn_off_all_leds()
            logging.info("Blink task has been cleaned up and all LEDs are turned off.")

    async def perform_blink(self):
        current_time = time.time()
        leds_to_remove = []
        led_color_map_on = {}
        led_color_map_off = {}

        for led_pin, last_update in self.active_led_pins.items():
            if current_time - last_update > self.timeout:
                leds_to_remove.append(led_pin)
                continue

            led_color_map_on[led_pin] = (255, 0, 0)  # Red color
            led_color_map_off[led_pin] = (0, 0, 0)   # Turn off

        for led_pin in leds_to_remove:
            del self.active_led_pins[led_pin]
            await self.turn_off_led(led_pin)
            logging.info(f"LED {led_pin} turned off due to timeout.")

        if not self.active_led_pins and not self.blocks and self.mode != 'block':
            logging.info("No active LEDs or blocks left to blink. Stopping blink task.")
            self.blink_event.set()
            return

        await self.set_leds_color_bulk(led_color_map_on)
        await asyncio.sleep(0.5)
        await self.set_leds_color_bulk(led_color_map_off)

    async def set_leds_color_bulk(self, led_color_map):
        strip_updates = {}
        for led_pin, color in led_color_map.items():
            strip_index, adjusted_led = self.get_strip_and_index(led_pin)
            strip = self.stripall[strip_index]
            if strip not in strip_updates:
                strip_updates[strip] = []
            strip_updates[strip].append((adjusted_led, Color(*color)))

        for strip, updates in strip_updates.items():
            for idx, color_value in updates:
                strip.setPixelColor(idx, color_value)
            await asyncio.get_event_loop().run_in_executor(None, strip.show)

    async def stop_blinking(self):
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
