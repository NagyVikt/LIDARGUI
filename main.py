# main.py

import threading
import logging
from network.run_server import run_server
from gui.led_controller import LEDController
import tkinter as tk

def start_server_thread():
    """
    Starts the asynchronous server in a separate thread.
    """
    run_server()

def start_gui():
    """
    Initializes and runs the Tkinter GUI.
    """
    # Initialize the Tkinter application
    root = tk.Tk()
    app = LEDController(root)

    def on_close():
        """
        Handles the GUI closure event.
        """
        logging.info("GUI closed. Exiting application...")
        root.destroy()

    # Bind the close event
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG for detailed logs
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("appdebug.log"),  # Logs to a file
            logging.StreamHandler()  # Logs to the console
        ]
    )

    # Start the server in a separate daemon thread
    server_thread = threading.Thread(target=start_server_thread)
    server_thread.daemon = True  # Ensures the thread exits when the main program does
    server_thread.start()
    logging.info("Server thread started.")

    # Start the GUI in the main thread
    start_gui()

    logging.info("Application shutdown complete.")
