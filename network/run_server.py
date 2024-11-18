# network/run_server.py

import asyncio
import logging
import serial_asyncio
from uvicorn import Config, Server

def run_server():
    """
    Initializes and runs the asynchronous server in its own event loop.
    This function is intended to be run in a separate thread.
    """
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    logging.info(f"Run_server thread event loop set: {loop}")

    # Import network.server after setting the event loop
    from network.server import app, blink_manager, stripall, LED_COUNT, SerialProtocol

    async def start_server():
        """
        Coroutine to start the serial connection and the Uvicorn server.
        """
        # Start the serial connection
        try:
            # Create serial connection with SerialProtocol
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop,
                lambda: SerialProtocol(blink_manager, LED_COUNT, stripall),
                '/dev/serial0',  # Replace with your actual serial port
                baudrate=9600
            )
            app.serial_protocol = protocol
            blink_manager.serial_protocol = protocol  # Assign to BlinkManager
            logging.info("Serial connection established and assigned to BlinkManager.")
        except Exception as e:
            logging.error(f"Failed to create serial connection: {e}")
            app.serial_protocol = None  # Indicate that serial is not available
            blink_manager.serial_protocol = None  # Also assign to BlinkManager

        # Create Uvicorn config
        config = Config(
            app=app,
            host="0.0.0.0",  # Change to '127.0.0.1' if external connections are not needed
            port=1080,
            loop="asyncio",
            log_level="info"
        )

        # Create the server
        server = Server(config=config)

        # Disable signal handlers (since running in a thread)
        server.install_signal_handlers = False

        # Start the server
        await server.serve()

    try:
        # Run the server coroutine until complete
        loop.run_until_complete(start_server())
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
    finally:
        # Close the event loop
        loop.close()
        logging.info("Server shutdown complete.")
