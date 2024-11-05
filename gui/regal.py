# gui/regal.py

import tkinter as tk
from tkinter import ttk
from functools import partial
import logging
from utils import ToolTip  # Ensure that utils.py contains the ToolTip class
from config.config import MAX_LEDS_ROW


class Regal:
    """Represents a Regal containing multiple LEDs with enhanced visual design."""

    def __init__(self, display_name, internal_name, led_data, controller, max_leds_per_row=MAX_LEDS_ROW):
        """
        Initialize a Regal frame with LEDs based on provided led_data.

        :param display_name: Name to display on the LabelFrame.
        :param internal_name: Internal identifier for the regal.
        :param led_data: Dictionary containing LED information (e.g., {'54': {'selected': False, 'order': None, 'FILE': 'path'}}).
        :param controller: Reference to the main LEDController.
        :param max_leds_per_row: Maximum number of LEDs per row in the GUI.
        """
        self.display_name = display_name
        self.internal_name = internal_name
        self.led_data = led_data
        self.controller = controller
        self.max_leds_per_row = max_leds_per_row

        # Create the LabelFrame for the Regal
        frame = ttk.LabelFrame(controller.led_frame, text=display_name)
        controller.regal_frames[internal_name] = frame
        frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Determine number of rows based on the number of LEDs and max LEDs per row
        total_leds = len(led_data)
        num_rows = (total_leds + max_leds_per_row - 1) // max_leds_per_row if max_leds_per_row else 1
        led_keys = list(led_data.keys())
        # Create LEDs

        for index, led_id in enumerate(led_keys):
            row = index // max_leds_per_row if max_leds_per_row else 0
            column = index % max_leds_per_row if max_leds_per_row else index

            # Generate unique led_key using internal_name and led_id
            led_key = controller.generate_unique_led_key(internal_name, led_id)

            # Create and store a BooleanVar for each LED
            selected = led_data[led_id].get('selected', False)
            led_var = tk.BooleanVar(value=selected)
            controller.led_vars[led_key] = led_var

            # Create a container frame for each LED with fixed dimensions
            led_container = ttk.Frame(frame, relief='groove', borderwidth=1, width=120, height=140)
            led_container.grid_propagate(False)  # Prevent resizing
            led_container.grid(row=row, column=column, padx=3, pady=3, sticky="nsew")

            # Configure grid weights for responsiveness
            frame.grid_rowconfigure(row, weight=1)
            frame.grid_columnconfigure(column, weight=1)

            # LED visual representation using Canvas
            led_canvas = tk.Canvas(led_container, width=40, height=40, highlightthickness=0)
            led_canvas.grid(row=0, column=0, pady=5)
            # Set initial color based on 'selected' state
            initial_color = 'green' if selected else 'grey'
            led_circle = led_canvas.create_oval(5, 5, 35, 35, fill=initial_color)
            controller.led_buttons[led_key] = (led_canvas, led_circle)

            # Bind click event to the canvas for toggling LED selection
            led_canvas.bind("<Button-1>", partial(controller.on_led_toggle_canvas, led_key))

            # Tooltip for the LED
            ToolTip(led_canvas, f"LED {led_id}")

            # Label for LED ID
            led_label = ttk.Label(led_container, text=f"LED {led_id}", font=("Helvetica", 10))
            led_label.grid(row=1, column=0)

            # Label for LED details (showing order if selected)
            order = led_data[led_id].get('order')
            if order is not None:
                detail_text = f"Order: {order}\nFILE: {led_data[led_id].get('FILE', '')}"
            else:
                detail_text = f"FILE: {led_data[led_id].get('FILE', '')}"
            detail_label = ttk.Label(led_container, text=detail_text, font=("Helvetica", 8), wraplength=100)
            detail_label.grid(row=2, column=0)
            controller.led_detail_labels[led_key] = detail_label

            # Edit Button (disabled if not selected)
            edit_button = ttk.Button(
                led_container,
                text="Edit",
                style='Edit.TButton',
                command=partial(controller.open_edit_window, led_key)
            )
            edit_button.grid(row=3, column=0, pady=(5, 0))
            if selected:
                edit_button.configure(state='normal')
            else:
                edit_button.configure(state='disabled')
            controller.led_edit_buttons[led_key] = edit_button

            # Prevent resizing of the led_container
            for r in range(4):
                led_container.rowconfigure(r, weight=0)
            led_container.rowconfigure(2, weight=1)  # Detail label can expand vertically
            led_container.columnconfigure(0, weight=1)

            # Logging for debugging
            logging.debug(f"Created LED key: '{led_key}' for Regal '{internal_name}' and LED ID '{led_id}'")
