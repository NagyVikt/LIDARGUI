# network/server.py

import asyncio
import logging
from quart import Quart, request, jsonify
from data.blink_manager import BlinkManager, Block
from network.serial_protocol import SerialProtocol
import serial_asyncio

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

LED_COUNT      = 69     # Number of LED pixels.
LED_PIN        = 18     # GPIO pin connected to the pixels.
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz
LED_DMA        = 10      # DMA channel to use for generating signal
LED_BRIGHTNESS = 255     # Brightness level
LED_INVERT     = False   # Invert signal
LED_CHANNEL    = 0       # GPIO channel

# Initialize LED strips
stripa = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
stripa.begin()
stripb = Adafruit_NeoPixel(LED_COUNT, 13, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, 1)
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

        a = await request.get_json()
        led_list = []
        control = []
        led_count = 0
        singleled = True
        start = False
        temporary_led = 0
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
        for shelves in a.get("data", {}).get("init", {}).get("shelves", {}):
            init = a["data"]["init"]["shelves"][shelves]
            control_value = int(init.get("controlled", 0))
            control.insert(int(shelves) - 1, control_value)

        # Determine control points based on shelves
        if len(control) == 1:
            control1 = control[0]
            stripa_selected = stripall[0]
            stripb_selected = None
        elif len(control) == 2:
            control1 = control[0]
            control2 = control[1]
            stripa_selected = stripall[0]
            stripb_selected = None
        else:
            control1 = control[0]
            control2 = control[1]
            control3 = control[2]
            stripa_selected = stripall[0]
            stripb_selected = stripall[1]

        # Function to update control LEDs
        async def controlcolorwipe(stripa, color):
            if len(control) == 1:
                stripa.setPixelColor(control1 - 1, color)
            else:
                stripa.setPixelColor(control1 - 1, color)
                stripa.setPixelColor(control2 - 1, color)
            await loop.run_in_executor(None, stripa.show)

        async def controlcolorwipe1(stripb, color):
            if stripb:
                stripb.setPixelColor(control3 - 1, color)
                await loop.run_in_executor(None, stripb.show)

        # Alternate control LED colors
        if counter % 2 == 0:
            if len(control) < 3:
                await controlcolorwipe(stripa_selected, Color(*COLOR_SINGLE))
            else:
                await controlcolorwipe(stripa_selected, Color(*COLOR_SINGLE))
                await controlcolorwipe1(stripb_selected, Color(*COLOR_SINGLE))
        else:
            if len(control) < 3:
                await controlcolorwipe(stripa_selected, Color(0, 0, 255))
            else:
                await controlcolorwipe(stripa_selected, Color(0, 0, 255))
                await controlcolorwipe1(stripb_selected, Color(0, 0, 255))

        # Function to update specific LEDs
        async def colorWipeSpecific(strip, color, led_number, k):
            if k == '2':
                strip.setPixelColor(led_number + control1 - 1, color)
            else:
                strip.setPixelColor(led_number - 1, color)
            await loop.run_in_executor(None, strip.show)

        # Process LED commands
        q = a.get("data", {}).get("shelves", {})
        for k, v in q.items():
            if k == '3':
                strip = stripall[1]
            else:
                strip = stripall[0]

            for ledid in v.get("leds", {}):
                led_count += 1
                c = v["leds"][ledid]
                if not start:
                    temporary_led = c
                    start = True
                else:
                    if temporary_led == c:
                        singleled = False

                # Write LED command to serial if available
                if hasattr(app, 'serial_protocol') and app.serial_protocol and app.serial_protocol.transport:
                    try:
                        led_number = led_offset * int(ledid)
                        command = f"LED {led_number}\n".encode('utf-8')
                        app.serial_protocol.transport.write(command)
                    except Exception as e:
                        logging.error(f"Error during serial write: {e}")
                else:
                    logging.warning("Serial protocol is not available. Skipping serial write.")

                # Handle LED activation and color
                if "on" in c and c["on"]:
                    if "blinking" in c and c["blinking"]:
                        led_number = led_offset * int(ledid)
                        await blink_manager.set_active_leds([led_number])
                    else:
                        if "color" in c:
                            color = str(c["color"])[1:]
                            led_number = led_offset * int(ledid)
                            try:
                                color_index = hex_codes.index(color)
                                color_rgb = rgb[color_index]
                                await colorWipeSpecific(strip, Color(*color_rgb), led_number, k)
                            except ValueError:
                                logging.error(f"Invalid color received: {color}")
                        else:
                            led_number = led_offset * int(ledid)
                            color_rgb = (0, 255, 0)
                            await colorWipeSpecific(strip, Color(*color_rgb), led_number, k)
                else:
                    led_number = led_offset * int(ledid)
                    await colorWipeSpecific(strip, Color(0, 0, 0), led_number, k)

        # Determine mode based on number of LEDs
        num_leds_on = len([v for shelves in q.values() for v in shelves["leds"].values() if v.get("on")])
        if num_leds_on == 1:
            logging.info("Activating SINGLE mode")
            # SINGLE mode: Already handled above
            pass
        elif num_leds_on > 1:
            logging.info("Activating BLOCK mode")
            # BLOCK mode
            led_order = [
                int(ledid)
                for shelves in q.values()
                for ledid, v in shelves["leds"].items()
                if v.get("on")
            ]
            await blink_manager.add_block(led_order)

        # Write 'Stop' command to serial if available
        if hasattr(app, 'serial_protocol') and app.serial_protocol and app.serial_protocol.transport:
            try:
                command = "Stop\n".encode('utf-8')
                app.serial_protocol.transport.write(command)
            except Exception as e:
                logging.error(f"Error during serial write: {e}")
        else:
            logging.warning("Serial protocol is not available. Skipping serial write.")

        logging.debug(f"Received payload: {a}")
        return jsonify(a)
    except Exception as e:
        logging.exception(f"An error occurred in /pick/leds: {e}")
        return jsonify({"error": str(e)}), 500
