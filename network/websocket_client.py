import asyncio
import logging
import websockets
from websockets.exceptions import ConnectionClosed
import threading
import traceback
import time

class WebSocketClient:
    def __init__(self, uri, message_processor_callback):
        self.uri = uri
        self.message_processor_callback = message_processor_callback
        self.loop = None  # Event loop will be created in the new thread
        self.message_queue = None
        self.thread = threading.Thread(target=self.start_loop, daemon=True)
        self.is_running = False
        self.reconnection_start_time = None
        self.max_reconnection_time = 3  # Maximum time in seconds to attempt reconnection

    def start_loop(self):
        """
        Start the asyncio event loop in a separate thread.
        """
        # Create a new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.is_running = True
        self.message_queue = asyncio.Queue()
        # Run the event loop
        try:
            self.loop.run_until_complete(self.websocket_handler())
        except Exception as e:
            logging.error(f"Error in event loop: {e}")
            logging.error(traceback.format_exc())
        finally:
            self.loop.close()

    async def listen_websocket(self):
        """
        Asynchronously listen to a WebSocket server and enqueue messages.
        """
        while self.is_running:
            try:
                # Start the reconnection timer if it's not already started
                if self.reconnection_start_time is None:
                    self.reconnection_start_time = time.monotonic()
                async with websockets.connect(
                    self.uri,
                    ping_interval=20,  # Send a ping every 20 seconds
                    ping_timeout=10    # Wait 10 seconds for a pong
                ) as websocket:
                    logging.info("WebSocket connection opened")
                    
                    # Reset reconnection timer upon successful connection
                    self.reconnection_start_time = None
                    while self.is_running:
                        try:
                            message = await websocket.recv()
                            logging.info(f"Received message from server: {message}")
                            await self.message_queue.put(message)
                        except ConnectionClosed as e:
                            logging.error(f"WebSocket connection closed: {e}")
                            logging.error(traceback.format_exc())
                            break
            except Exception as e:
                logging.error(f"WebSocket encountered error: {e}")
                logging.error(traceback.format_exc())

            if self.is_running:
                # Calculate the elapsed reconnection time
                elapsed_time = time.monotonic() - self.reconnection_start_time
                if elapsed_time >= self.max_reconnection_time:
                    logging.error("Max reconnection time exceeded. Stopping client.")
                    self.is_running = False
                    break
                else:
                    logging.info("Attempting to reconnect to WebSocket...")
                    # Sleep briefly before retrying to avoid tight loop
                    await asyncio.sleep(0.5)

    async def websocket_handler(self):
        """
        Handle incoming WebSocket messages and process specific commands.
        """
        listen_task = asyncio.create_task(self.listen_websocket())

        while self.is_running:
            try:
                message = await self.message_queue.get()
                # Pass the message to the main thread via the callback
                self.safe_message_processor_callback(message)
                self.message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in websocket_handler: {e}")
                logging.error(traceback.format_exc())

        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass

    def safe_message_processor_callback(self, message):
        try:
            self.message_processor_callback(message)
        except Exception as e:
            logging.error(f"Error in message_processor_callback: {e}")
            logging.error(traceback.format_exc())

    def start(self):
        """
        Start the WebSocket client.
        """
        self.thread.start()

    def stop(self):
        """
        Stop the WebSocket client and close the event loop.
        """
        self.is_running = False
        # Stop the event loop safely
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
