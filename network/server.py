# server.py

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

LED_COUNT = 255    # Number of LED pixels.
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
blink_manager = BlinkManager(stripall, LED_COUNT, shelf_led_count=255)

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

        # Turn off all LEDs before processing new data
        await blink_manager.turn_off_all_leds()

        # Extract control values and prepare control LEDs
        init_shelves = data.get("data", {}).get("init", {}).get("shelves", {})
        controlled_values = {}
        for shelf_id, init_info in init_shelves.items():
            control_value = int(init_info.get("controlled", 0))
            controlled_values[shelf_id] = control_value

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
        for shelf_id, control_value in controlled_values.items():
            strip_index = 0 if int(shelf_id) <= 2 else 1  # Adjust based on your configuration
            strip = stripall[strip_index]
            await controlcolorwipe(strip, control_color, control_value)

        # Extract led_sequence from the payload
        led_sequence = data.get("data", {}).get("led_sequence", [])

        # Handle non-blinking LEDs (BLOCK mode)
        if led_sequence:
            await blink_manager.add_block(
                led_sequence=led_sequence,
                controlled_values=controlled_values,
                color_green=COLOR_BLOCK_FIRST,
                color_blue=COLOR_BLOCK_REST
            )
            logging.info(f"Added block with LEDs: {led_sequence}")

        # Handle blinking LEDs (SINGLE mode)
        # If you have blinking LEDs in your payload, handle them here

        # Write LED command to serial if available
        if hasattr(app, 'serial_protocol') and app.serial_protocol and app.serial_protocol.transport:
            try:
                # If you need to send commands to the serial device, implement them here
                pass
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


