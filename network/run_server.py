# network/run_server.py

import asyncio
import logging
from network.server import app, blink_manager, stripall, LED_COUNT, SerialProtocol
import serial_asyncio
from uvicorn import Config, Server

def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_server():
        # Start the serial connection
        try:
            # Pass the loop explicitly
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop,
                lambda: SerialProtocol(blink_manager, LED_COUNT, stripall),
                '/dev/serial0',
                baudrate=9600
            )
            app.serial_protocol = protocol
            logging.info("Serial connection established.")
        except Exception as e:
            logging.error(f"Failed to create serial connection: {e}")
            app.serial_protocol = None  # Indicate that serial is not available

        # Create Uvicorn config
        config = Config(
            app=app,
            host="127.0.0.1",
            port=1080,
            loop="asyncio",
            log_level="info"
        )

        # Create the server
        server = Server(config=config)

        # Disable signal handlers
        server.install_signal_handlers = False

        # Start the server
        await server.serve()

    try:
        loop.run_until_complete(start_server())
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
    finally:
        loop.close()
        logging.info("Server shutdown complete.")
