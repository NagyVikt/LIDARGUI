# main.py

import threading
import logging
from network.run_server import run_server
from gui.led_controller import LEDController
import tkinter as tk

def start_server_thread():
    run_server()

def start_gui():
    # Initialize the Tkinter application
    root = tk.Tk()
    app = LEDController(root)

    def on_close():
        logging.info("GUI closed. Exiting application...")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("appdebug.log"),
            logging.StreamHandler()
        ]
    )

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server_thread)
    server_thread.daemon = True  # Ensure the thread exits when the main program does
    server_thread.start()
    logging.info("Server thread started.")

    # Start the GUI in the main thread
    start_gui()

    logging.info("Application shutdown complete.")
