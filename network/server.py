# network/server.py

import asyncio
import logging
from quart import Quart, request, jsonify
from data.blink_manager import BlinkManager, Block
from network.serial_protocol import SerialProtocol
import serial_asyncio
from config.config import WINDOWS

# Initialize the Quart app
app = Quart(__name__)
app.config['JSON_SORT_KEYS'] = False

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("appdebug.log"),
        logging.StreamHandler()
    ]
)

# Function to check if running on Raspberry Pi

# LED Initialization Parameters
is_it_Pi400 = True  # False for using PI4, True for using Pi400
if WINDOWS:
    from utils.mock_rpi_ws281x import Adafruit_NeoPixel
else:
    # Initialize LED strips and colors
    if is_it_Pi400 == False:
        from neopixel import *
        logging.info("WE ARE USING Pi4")
        hex_codes = ['FF0000', '00FF00', '0000FF', '00AA00']  # Hex codes for colors
        rgb = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (0, 200, 0)]  # RGB translations for Pi4
    else:
        from rpi_ws281x import *
        logging.info("WE ARE USING Pi400")
        hex_codes = ['FF0000', '00FF00', '0000FF', '00AA00']  # Hex codes for colors
        rgb = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 200, 0)]  # RGB translations

# Define color codes and RGB values
hex_codes = ['FF0000', '00FF00', '0000FF', '00AA00']
rgb = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 170, 0)]

LED_COUNT = 69     # Number of LED pixels.
LED_PIN = 18       # GPIO pin connected to the pixels.
LED_PIN_B = 13     # GPIO pin connected to the pixels (for stripb)
LED_FREQ_HZ = 800000  # LED signal frequency in hertz
LED_DMA = 10       # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Brightness level
LED_INVERT = False  # Invert signal
LED_CHANNEL = 0     # GPIO channel

# Initialize LED strips
stripa = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
stripa.begin()
stripb = Adafruit_NeoPixel(LED_COUNT, LED_PIN_B, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, 1)
stripb.begin()
stripall = [stripa, stripb]

# Initialize BlinkManager
blink_manager = BlinkManager(stripall, LED_COUNT, shelf_led_count=69)

counter = 0               # To alternate the color of control lights
led_offset = 1            # Adjusting strip to rack
is_pin_needed = False     # Pin by light necessity flag

logging.info(f"PIN BY LIGHT IS SET TO: {is_pin_needed}")

# Define additional colors
COLOR_SINGLE = (0, 255, 0)   # Green for SINGLE mode
COLOR_BLOCK_FIRST = (0, 255, 0)  # Green for first LED in BLOCK mode
COLOR_BLOCK_REST = (0, 0, 255)   # Blue for other LEDs in BLOCK mode

@app.route('/')
async def hello_world():
    return jsonify(result="Hello, Quart server is running with asyncio.")

# Route to handle LED activation
@app.route('/pick/leds', methods=['POST'])
async def pick_leds_post():
    try:
        global counter, is_pin_needed

        data = await request.get_json()
        loop = asyncio.get_event_loop()

        # Initialize serial and write 'Start' command if available
        if hasattr(app, 'serial_protocol') and app.serial_protocol and app.serial_protocol.transport:
            try:
                command = "Start\n".encode('utf-8')
                app.serial_protocol.transport.write(command)
            except Exception as e:
                logging.error(f"Error during serial write: {e}")
        else:
            logging.warning("Serial protocol is not available. Skipping serial write.")

        # Processing shelves and control logic
        shelves_data = data.get("data", {}).get("shelves", {})
        init_shelves = data.get("data", {}).get("init", {}).get("shelves", {})

        # Turn off all LEDs before processing new data
        await blink_manager.turn_off_all_leds()

        # Extract control values and prepare control LEDs
        control_values = {}
        for shelf_id, init_info in init_shelves.items():
            control_value = int(init_info.get("controlled", 0))
            control_values[shelf_id] = control_value

        # Alternate control LED colors
        counter += 1
        if counter % 2 == 0:
            control_color = Color(*COLOR_SINGLE)
        else:
            control_color = Color(0, 0, 255)

        # Function to update control LEDs
        async def controlcolorwipe(strip, color, control_led):
            strip.setPixelColor(control_led - 1, color)
            await loop.run_in_executor(None, strip.show)

        # Update control LEDs
        for shelf_id, control_value in control_values.items():
            strip_index = 0 if int(shelf_id) <= 2 else 1  # Adjust based on your configuration
            strip = stripall[strip_index]
            await controlcolorwipe(strip, control_color, control_value)

        # Process LED commands
        for shelf_id, shelf_data in shelves_data.items():
            init_info = init_shelves.get(shelf_id, {})
            controlled_value = int(init_info.get("controlled", 0))
            leds_info = shelf_data.get("leds", {})

            # Prepare lists for blinking and non-blinking LEDs
            blinking_leds = []
            non_blinking_leds = []
            for led_id_str, led_data in leds_info.items():
                led_id = int(led_id_str)
                if led_data.get("on"):
                    if led_data.get("blinking"):
                        blinking_leds.append(led_id)
                    else:
                        non_blinking_leds.append(led_id)

            # Adjust LED numbers by adding controlled_value
            adjusted_blinking_leds = [led + controlled_value for led in blinking_leds]
            adjusted_non_blinking_leds = [led + controlled_value for led in non_blinking_leds]

            # Handle blinking LEDs (SINGLE mode)
            if adjusted_blinking_leds:
                await blink_manager.set_active_leds(adjusted_blinking_leds)
                logging.info(f"Shelf {shelf_id}: Activated blinking LEDs {adjusted_blinking_leds}")

            # Handle non-blinking LEDs (BLOCK mode)
            if adjusted_non_blinking_leds:
                await blink_manager.add_block(
                    shelf_id=shelf_id,
                    controlled_value=controlled_value,
                    led_list=non_blinking_leds,  # Pass raw LED numbers; Block class adjusts them
                    color_green=COLOR_BLOCK_FIRST,
                    color_blue=COLOR_BLOCK_REST
                )
                logging.info(f"Shelf {shelf_id}: Added block with LEDs {adjusted_non_blinking_leds}")

            # Handle colors for non-blinking LEDs
            for led_id_str, led_data in leds_info.items():
                led_id = int(led_id_str)
                if led_data.get("on") and not led_data.get("blinking"):
                    color_hex = led_data.get("color", "#00FF00")[1:]  # Remove '#' from color code
                    try:
                        color_index = hex_codes.index(color_hex.upper())
                        color_rgb = rgb[color_index]
                    except ValueError:
                        color_rgb = (0, 255, 0)  # Default to green if color not found
                        logging.error(f"Invalid color received: {color_hex}, defaulting to green.")
                    adjusted_led = led_id + controlled_value
                    await blink_manager.set_led_color(adjusted_led, color_rgb)
                    logging.info(f"Shelf {shelf_id}: Set LED {adjusted_led} to color {color_rgb}")

            # Write LED command to serial if available
            if hasattr(app, 'serial_protocol') and app.serial_protocol and app.serial_protocol.transport:
                try:
                    for led_id in blinking_leds + non_blinking_leds:
                        led_number = led_offset * led_id + controlled_value
                        command = f"LED {led_number}\n".encode('utf-8')
                        app.serial_protocol.transport.write(command)
                except Exception as e:
                    logging.error(f"Error during serial write: {e}")
            else:
                logging.warning("Serial protocol is not available. Skipping serial write.")

        # Write 'Stop' command to serial if available
        if hasattr(app, 'serial_protocol') and app.serial_protocol and app.serial_protocol.transport:
            try:
                command = "Stop\n".encode('utf-8')
                app.serial_protocol.transport.write(command)
            except Exception as e:
                logging.error(f"Error during serial write: {e}")
        else:
            logging.warning("Serial protocol is not available. Skipping serial write.")

        logging.debug(f"Received payload: {data}")
        return jsonify(data)
    except Exception as e:
        logging.exception(f"An error occurred in /pick/leds: {e}")
        return jsonify({"error": str(e)}), 500

# Keep the rest of the functions intact



