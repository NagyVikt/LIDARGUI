# network/http_client.py

import aiohttp
import asyncio
import logging
from tkinter import messagebox


# Mapping from shelf names to integer IDs
SHELF_NAME_TO_ID = {
    'Regal1': 1,
    'Regal2': 2,
    'Benti Regal': 1,
    # Add other shelf mappings here as needed
}



async def send_led_control_request_async(selected_project, selected_order, led_id_to_regal, status_var, progress_bar):
    """Asynchronous function to send LED control request."""
    if not selected_project:
        messagebox.showwarning("No Project Selected", "Please select a project before activating LEDs.")
        return

    url = "http://172.26.202.87:1080/pick/leds"
    shelves_payload = {}

    if not selected_order:
        messagebox.showwarning("No Selection", "Please select at least one LED to activate.")
        return

    for order_num, led_key in enumerate(selected_order, start=1):
        shelf_identifier = led_id_to_regal.get(led_key)
        
        if shelf_identifier is None:
            logging.error(f"LED key '{led_key}' does not have a corresponding shelf in led_id_to_regal.")
            messagebox.showerror("Error", f"LED key '{led_key}' does not have a corresponding shelf.")
            return

        # Map shelf name to shelf ID using the centralized mapping
        if isinstance(shelf_identifier, str):
            shelf_number = SHELF_NAME_TO_ID.get(shelf_identifier)
            if shelf_number is None:
                logging.error(f"Unknown shelf name '{shelf_identifier}' for LED key '{led_key}'.")
                messagebox.showerror("Error", f"Unknown shelf name '{shelf_identifier}' for LED key '{led_key}'.")
                return
        else:
            # Assume it's already an integer
            shelf_number = shelf_identifier

        if not isinstance(shelf_number, int):
            logging.error(f"Shelf number for LED key '{led_key}' is not an integer: {shelf_number}")
            messagebox.showerror("Error", f"Shelf number for LED key '{led_key}' is invalid.")
            return

        led_id = led_key.split('_')[1]
        if shelf_number not in shelves_payload:
            shelves_payload[shelf_number] = {'leds': {}}
        shelves_payload[shelf_number]['leds'][str(led_id)] = {
            'on': True,
            'blinking': False,
            'order': order_num
        }

    payload = {
        "data": {
            "init": {
                "shelves": {
                    shelf_id: {"controlled": 90} for shelf_id in shelves_payload.keys()
                }
            },
            "shelves": shelves_payload
        }
    }

    # Log the payload for debugging
    logging.debug(f"Payload to be sent: {payload}")

    # Update status
    status_var.set("Sending LED activation request...")
    progress_bar.start()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                response.raise_for_status()
                try:
                    response_data = await response.json()
                    logging.info(f"Response JSON: {response_data}")
                    messagebox.showinfo("Success", f"LEDs controlled successfully:\n{response_data}")
                except aiohttp.ContentTypeError:
                    # Response is not JSON
                    response_text = await response.text()
                    logging.warning("Response content is not valid JSON.")
                    logging.warning(f"Response Text: {response_text}")
                    messagebox.showwarning("Warning", f"Response is not JSON:\n{response_text}")
    except aiohttp.ClientResponseError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        response_text = await http_err.response.text() if http_err.response else ""
        logging.error(f"Response Text: {response_text}")
        messagebox.showerror("HTTP Error", f"HTTP error occurred:\n{http_err}\n{response_text}")
    except asyncio.TimeoutError:
        logging.error("The request timed out.")
        messagebox.showerror("Timeout Error", "The request timed out.")
    except aiohttp.ClientError as err:
        logging.error(f"An error occurred: {err}")
        messagebox.showerror("Error", f"An error occurred:\n{err}")
    finally:
        status_var.set("")
        progress_bar.stop()
