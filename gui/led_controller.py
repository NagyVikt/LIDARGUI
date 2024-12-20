import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import asyncio
import threading
import logging
import os
import json
from functools import partial
from queue import Queue, Empty
from aiohttp import web, ClientSession
import aiofiles
import colorsys
from config import config

# ============================
# ToolTip Class (Utility)
# ============================

class ToolTip:
    """
    It creates a tooltip for a given widget as the mouse goes on it.
    """
    def __init__(self, widget, text='widget info'):
        self.waittime = 500  # milliseconds
        self.wraplength = 180  # pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<ButtonPress>", self.on_leave)
        self.id = None
        self.tw = None

    def on_enter(self, event=None):
        self.schedule()

    def on_leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        _id = self.id
        self.id = None
        if _id:
            self.widget.after_cancel(_id)

    def showtip(self, event=None):
        x = y = 0
        # Position the tooltip below and to the right of the widget
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

# ============================
# Configuration and Mock Implementations
# ============================


def save_settings(self, led_control, max_leds_row, window):
    """Save the settings and update the configuration."""
    # Update the settings dictionary in config module
    config.settings["LED_CONTROL"] = led_control
    config.settings["MAX_LEDS_ROW"] = max_leds_row
    # WINDOWS is not saved because it's auto-detected

    # Save the settings to file
    config.save_settings(config.settings)

    # Update the variables in config module
    config.LED_CONTROL = led_control
    config.MAX_LEDS_ROW = max_leds_row
    # WINDOWS remains as is

    # Close the settings window
    window.destroy()

    # Notify the user
    messagebox.showinfo("Settings Saved", "Configuration settings have been updated.")

    # Update internal variables
    self.LED_CONTROL = config.LED_CONTROL
    self.MAX_LEDS_ROW = config.MAX_LEDS_ROW
    # self.WINDOWS remains unchanged

    # Recreate the regal frames with the new settings
    self.recreate_regal_frames()


# Mock for data.project_manager
async def get_available_projects():
    """Return a list of available project names."""
    # For demonstration, return a static list
    await asyncio.sleep(0.1)  # Simulate async operation
    return ["Project_Two_Regals", "Project_Benti_Regal"]

async def load_project_mapping_async(project_name, base_dir):
    """
    Load project data from a JSON file.
    Assumes that project JSON files are located in 'projects' directory.
    """
    project_file = os.path.join(base_dir, "projects", f"{project_name}.json")
    if not os.path.isfile(project_file):
        # Create a default project file for demonstration
        os.makedirs(os.path.dirname(project_file), exist_ok=True)
        default_data = {
            "Regal1": {
                "1": {"FILE": "data/regal1_led1.png"},
                "2": {"FILE": "data/regal1_led2.png"},
                "3": {"FILE": "data/regal1_led3.png"}
            },
            "Regal2": {
                "1": {"FILE": "data/regal2_led1.png"},
                "2": {"FILE": "data/regal2_led2.png"},
                "3": {"FILE": "data/regal2_led3.png"}
            },
            "selected_order": []
        }
        async with aiofiles.open(project_file, mode='w') as f:
            content = json.dumps(default_data, indent=4)
            await f.write(content)

    async with aiofiles.open(project_file, mode='r') as f:
        content = await f.read()
        data = json.loads(content)
    return data

async def save_project_json_async(project_name, led_data, base_dir):
    """
    Save project data to a JSON file.
    Saves to 'projects' directory.
    """
    project_file = os.path.join(base_dir, "projects", f"{project_name}.json")
    os.makedirs(os.path.dirname(project_file), exist_ok=True)
    async with aiofiles.open(project_file, mode='w') as f:
        content = json.dumps(led_data, indent=4)
        await f.write(content)

# ============================
# Mock Regal Class
# ============================

class Regal:
    """Mock implementation of the Regal class."""
    def __init__(self, display_name, internal_name, led_data, controller, max_leds_per_row):
        self.display_name = display_name
        self.internal_name = internal_name
        self.led_data = led_data
        self.controller = controller
        self.max_leds_per_row = max_leds_per_row

        # Create a container frame for the regal
        self.container = ttk.LabelFrame(controller.led_frame, text=self.display_name)
        self.container.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        controller.regal_frames[self.internal_name] = self.container

        # Populate LEDs
        self.populate_leds()

    def populate_leds(self):
        """Populate LEDs in the regal."""
        row = 0
        col = 0
        for led_id, led_info in self.led_data.items():
            led_key = self.controller.generate_unique_led_key(self.internal_name, led_id)
            led_var = tk.IntVar(value=0)
            self.controller.led_vars[led_key] = led_var

            # Create a frame for each LED
            led_frame = ttk.Frame(self.container)
            led_frame.grid(row=row, column=col, padx=5, pady=5)

            # Create a canvas to represent the LED
            led_canvas = tk.Canvas(led_frame, width=30, height=30)  # Increased size for better visibility
            led_circle = led_canvas.create_oval(5, 5, 25, 25, fill='grey')
            # Add LED number inside the circle
            led_canvas.create_text(15, 15, text=str(led_id), fill='white', font=('Helvetica', 10, 'bold'))
            led_canvas.pack()
            self.controller.led_buttons[led_key] = (led_canvas, led_circle)

            # Bind click events
            led_canvas.bind("<Button-1>", lambda event, key=led_key: self.controller.on_led_toggle_canvas(key, event))
            led_canvas.bind("<Button-3>", lambda event, key=led_key: self.controller.on_led_toggle_canvas(key, event))
            ToolTip(led_canvas, "Left-click to select LED\nRight-click to deselect LED")

            # LED detail label
            detail_label = ttk.Label(led_frame, text=f"FILE: {led_info.get('FILE', '')}")
            detail_label.pack()
            self.controller.led_detail_labels[led_key] = detail_label

            # Edit button
            edit_button = ttk.Button(
                led_frame,
                text="Edit",
                command=lambda key=led_key: self.controller.open_edit_window(key),
                state='disabled',
                style='Edit.TButton'
            )
            edit_button.pack(pady=2)
            self.controller.led_edit_buttons[led_key] = edit_button

            # Next LED position
            col += 1
            if col >= self.max_leds_per_row:
                col = 0
                row += 1

# ============================
# LEDController Class
# ============================

class LEDController:
    def __init__(self, master):
        self.master = master
        self.master.title("LED Control Panel")
        self.master.geometry("1600x700")
        self.master.minsize(1200, 600)

        # Define base directory
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        # Initialize variables
        self.current_mode = 'two_regals'
        self.selected_order = []
        self.led_vars = {}
        self.led_buttons = {}  # Store references to LED canvas and circle
        self.led_detail_labels = {}
        self.led_edit_buttons = {}
        self.led_id_to_regal = {}
        self.regal_frames = {}
        self.MAX_SELECTION = 100

        self.LED_CONTROL = config.LED_CONTROL
        self.MAX_LEDS_ROW = config.MAX_LEDS_ROW
        self.WINDOWS = config.WINDOWS

        # Initialize stacks for undo and redo
        self.undo_stack = []
        self.redo_stack = []

        # Selected project
        self.selected_project = None
        self.panel_visible = True  # Control panel is visible by default
        self.is_loading_project = False

        # LED data loaded from JSON
        self.led_data = {}  # Key: regal_name, Value: {led_id: {...}, ...}

        # Currently selected LED for editing
        self.current_edit_led = None

        # Configure logging
        self.configure_logging()

        # Initialize asyncio event loop in a separate thread
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.start_event_loop, daemon=True)
        self.loop_thread.start()

        # Queue for inter-thread communication
        self.queue = Queue()

        # Start the queue processing
        self.process_queue()

        # Initialize aiohttp session
        self.session = ClientSession(loop=self.loop)

        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use('clam')  # You can choose other themes like 'alt', 'default', 'classic')

        # Define custom styles
        self.define_styles()

        # Setup GUI components
        self.setup_gui()

        # Handle application closure
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_logging(self):
        """Configure logging for the application."""
        logging.basicConfig(
            level=logging.DEBUG,  # Set to DEBUG for detailed logs
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def start_event_loop(self):
        """Start the asyncio event loop."""
        asyncio.set_event_loop(self.loop)

        # Set up aiohttp web server
        app = web.Application()
        app.router.add_post('/block_completed', self.handle_block_completed)
        runner = web.AppRunner(app)
        self.loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, 'localhost', 8080)
        self.loop.run_until_complete(site.start())
        logging.info("Aiohttp web server started on port 8080")

        self.loop.run_forever()

    async def handle_block_completed(self, request):
        """Handle block_completed notification from blink_manager."""
        logging.info("Received block_completed notification")
        # Put a message into the queue to be processed by the GUI thread
        self.queue.put(("block_completed", None))
        return web.Response(text="OK")

    def open_settings_window(self):
        """Open a window to edit configuration settings."""
        # Create a new Toplevel window
        settings_window = tk.Toplevel(self.master)
        settings_window.title("Settings")
        settings_window.geometry("300x200")
        settings_window.grab_set()  # Make the window modal

        # Define variables to hold the settings
        led_control_var = tk.IntVar(value=config.LED_CONTROL)
        max_leds_row_var = tk.IntVar(value=config.MAX_LEDS_ROW)
        windows_var = tk.BooleanVar(value=config.WINDOWS)

        # LED_CONTROL
        led_control_frame = ttk.Frame(settings_window)
        led_control_frame.pack(pady=5, padx=10, fill=tk.X)
        led_control_label = ttk.Label(led_control_frame, text="LED_CONTROL:")
        led_control_label.pack(side=tk.LEFT)
        led_control_entry = ttk.Entry(led_control_frame, textvariable=led_control_var)
        led_control_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # MAX_LEDS_ROW
        max_leds_row_frame = ttk.Frame(settings_window)
        max_leds_row_frame.pack(pady=5, padx=10, fill=tk.X)
        max_leds_row_label = ttk.Label(max_leds_row_frame, text="MAX_LEDS_ROW:")
        max_leds_row_label.pack(side=tk.LEFT)
        max_leds_row_entry = ttk.Entry(max_leds_row_frame, textvariable=max_leds_row_var)
        max_leds_row_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # WINDOWS
        windows_frame = ttk.Frame(settings_window)
        windows_frame.pack(pady=5, padx=10, fill=tk.X)
        windows_label = ttk.Label(windows_frame, text="WINDOWS:")
        windows_label.pack(side=tk.LEFT)
        windows_check = ttk.Checkbutton(windows_frame, variable=windows_var)
        windows_check.pack(side=tk.LEFT)

        # Save Button
        save_button = ttk.Button(
            settings_window,
            text="Save",
            command=lambda: self.save_settings(
                led_control_var.get(),
                max_leds_row_var.get(),
                windows_var.get(),
                settings_window
            )
        )
        save_button.pack(pady=10)
        ToolTip(save_button, "Save configuration settings")

    def save_settings(self, led_control, max_leds_row, windows, window):
        """Save the settings and update the configuration."""
        # Update the config settings
        config.settings["LED_CONTROL"] = led_control
        config.settings["MAX_LEDS_ROW"] = max_leds_row
        config.settings["WINDOWS"] = windows

        # Update the variables in config module
        config.LED_CONTROL = led_control
        config.MAX_LEDS_ROW = max_leds_row
        config.WINDOWS = windows

        # Save the settings to file
        config.save_settings(config.settings)

        # Close the settings window
        window.destroy()

        # Notify the user
        messagebox.showinfo("Settings Saved", "Configuration settings have been updated.")

        # Update internal variables
        self.LED_CONTROL = config.LED_CONTROL
        self.MAX_LEDS_ROW = config.MAX_LEDS_ROW
        self.WINDOWS = config.WINDOWS

        # Recreate the regal frames with the new settings
        self.recreate_regal_frames()

    def recreate_regal_frames(self):
        """Recreate regal frames using the updated settings."""
        logging.info("Recreating regal frames with updated settings.")

        # Clear existing regals if any
        for regal_name, container in self.regal_frames.items():
            container.destroy()
        self.regal_frames.clear()
        self.led_vars.clear()
        self.led_detail_labels.clear()
        self.led_edit_buttons.clear()
        self.led_id_to_regal.clear()
        self.selected_order.clear()  # Clear selections when changing settings

        # Recreate Regals with updated MAX_LEDS_ROW
        for regal_name, leds in self.led_data.items():
            if regal_name.lower() == "selected_order":
                continue  # Skip the selected_order key
            Regal(
                display_name=regal_name,
                internal_name=regal_name,
                led_data=leds,
                controller=self,
                max_leds_per_row=self.MAX_LEDS_ROW  # Pass the required argument
            )
            # Map LED keys to regal names
            for led_id in leds.keys():
                led_key = self.generate_unique_led_key(regal_name, led_id)
                self.led_id_to_regal[led_key] = regal_name

        # After recreating regals, re-initialize selections and update UI
        self.initialize_led_selections()
        self.update_all_labels()
        self.update_selection_count()
        self.update_selected_order_listbox()
        logging.info("Regal frames recreated successfully.")

    def define_styles(self):
        """Define custom styles for the application."""
        # Define styles with a modern color palette and consistent fonts
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=("Helvetica", 11))
        self.style.configure('TButton', font=("Helvetica", 11))
        self.style.configure('TEntry', font=("Helvetica", 11))

        # Define styles for specific buttons
        button_styles = {
            'Activate.TButton': {'foreground': 'white', 'background': '#28a745', 'font': ('Helvetica', 12, 'bold')},
            'Undo.TButton': {'foreground': 'white', 'background': '#6c757d', 'font': ('Helvetica', 12, 'bold')},
            'Redo.TButton': {'foreground': 'white', 'background': '#17a2b8', 'font': ('Helvetica', 12, 'bold')},
            'SwitchMode.TButton': {'foreground': 'white', 'background': '#343a40', 'font': ('Helvetica', 12, 'bold')},
            'Clear.TButton': {'foreground': 'white', 'background': '#fd7e14', 'font': ('Helvetica', 12, 'bold')},
            'Exit.TButton': {'foreground': 'white', 'background': '#dc3545', 'font': ('Helvetica', 12, 'bold')},
            'Edit.TButton': {'foreground': 'white', 'background': '#ff0000', 'font': ('Helvetica', 10, 'bold')},
            'EditSave.TButton': {'foreground': 'white', 'background': '#007bff', 'font': ('Helvetica', 12, 'bold')},
            'Remove.TButton': {'foreground': 'white', 'background': '#dc3545', 'font': ('Helvetica', 10, 'bold')},
        }

        for style_name, cfg in button_styles.items():
            self.style.configure(style_name, **cfg)
            # Define hover effects
            hover_bg = self.darken_color(cfg['background'], 0.9)
            self.style.map(style_name, foreground=[('active', 'white')],
                           background=[('active', hover_bg)])

    def darken_color(self, color, factor=0.9):
        """Darken the given color by the given factor."""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16)/255.0 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(*rgb)
        l = max(0, min(1, l * factor))
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

    def generate_unique_led_key(self, regal_name, led_id):
        """Generate a unique key for each LED based on its regal and ID."""
        return f"{regal_name}_{led_id}"

    def setup_gui(self):
        """Setup the main GUI components."""
        # Main PanedWindow
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Control Panel Frame
        self.control_panel = ttk.Frame(self.paned_window, width=400)
        self.paned_window.add(self.control_panel, weight=0)

        # LED Canvas Frame
        self.led_canvas_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.led_canvas_frame, weight=1)

        # Create the canvas
        self.led_canvas = tk.Canvas(self.led_canvas_frame, bg="#ffffff")
        self.led_canvas.grid(row=0, column=0, sticky='nsew')

        # Create the scrollbars
        self.led_v_scrollbar = ttk.Scrollbar(self.led_canvas_frame, orient="vertical", command=self.led_canvas.yview)
        self.led_v_scrollbar.grid(row=0, column=1, sticky='ns')

        self.led_h_scrollbar = ttk.Scrollbar(self.led_canvas_frame, orient="horizontal", command=self.led_canvas.xview)
        self.led_h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure the canvas to use the scrollbars
        self.led_canvas.configure(yscrollcommand=self.led_v_scrollbar.set, xscrollcommand=self.led_h_scrollbar.set)

        # Configure grid weights
        self.led_canvas_frame.grid_rowconfigure(0, weight=1)
        self.led_canvas_frame.grid_columnconfigure(0, weight=1)

        # LED Frame inside Canvas
        self.led_frame = ttk.Frame(self.led_canvas)
        self.led_canvas.create_window((0, 0), window=self.led_frame, anchor="nw")

        # Bind to the frame inside the canvas
        self.led_frame.bind('<Configure>', self.on_frame_configure)

        # No Project Selected Label
        self.no_project_label = ttk.Label(
            self.led_frame,
            text="Please select a project to view the LED layout.",
            font=("Helvetica", 18),
            foreground="red"
        )
        self.no_project_label.pack(pady=20)

        # Control Panel Components
        self.build_control_panel()

        # Status Bar
        self.build_status_bar()

    def on_frame_configure(self, event):
        """Update scroll region when the inner frame is resized."""
        self.led_canvas.configure(scrollregion=self.led_canvas.bbox("all"))

    def build_control_panel(self):
        """Builds the control panel UI."""
        # Project Selection Section
        project_frame = ttk.LabelFrame(self.control_panel, text="Select Project")
        project_frame.pack(pady=10, padx=10, fill=tk.X)

        self.project_var = tk.StringVar()
        project_label = ttk.Label(project_frame, text="Choose a project:")
        project_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.project_combobox = ttk.Combobox(project_frame, textvariable=self.project_var, state="readonly")
        self.project_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.project_combobox.bind("<<ComboboxSelected>>", self.on_project_selected)
        ToolTip(self.project_combobox, "Select a project to proceed")

        project_frame.columnconfigure(1, weight=1)

        # Title Label
        title_label = ttk.Label(self.control_panel, text="Select LEDs to Activate", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=(10, 5))

        # Mode Indicator
        self.mode_var = tk.StringVar(value=f"Current Mode: {self.current_mode.replace('_', ' ').title()}")
        mode_label = ttk.Label(self.control_panel, textvariable=self.mode_var, font=("Helvetica", 12, "italic"))
        mode_label.pack(pady=5)

        # Selection Count
        self.selection_var = tk.StringVar(value=f"Selected LEDs: 0 / {self.MAX_SELECTION}")
        selection_label = ttk.Label(self.control_panel, textvariable=self.selection_var, font=("Helvetica", 12))
        selection_label.pack(pady=5)

        # Selected Order Listbox Section
        order_frame = ttk.LabelFrame(self.control_panel, text="Selected LEDs Order")
        order_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Listbox with drag-and-drop
        self.order_listbox = tk.Listbox(order_frame, height=10, selectmode=tk.BROWSE)
        self.order_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5), pady=5)

        # Enable drag-and-drop for the Listbox
        self.enable_listbox_drag_and_drop()

        # Scrollbar for listbox
        order_scrollbar = ttk.Scrollbar(order_frame, orient="vertical", command=self.order_listbox.yview)
        order_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.order_listbox.configure(yscrollcommand=order_scrollbar.set)

        # Remove Button
        remove_button = ttk.Button(order_frame, text="Remove Selected", command=self.remove_selected_order, style='Remove.TButton')
        remove_button.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5)
        ToolTip(remove_button, "Remove the selected LED from the order")

        # Control Buttons Frame
        buttons_frame = ttk.Frame(self.control_panel)
        buttons_frame.pack(pady=10, padx=10, fill=tk.X)

        # Clear Selections Button
        clear_button = ttk.Button(buttons_frame, text="Clear Selections", command=self.clear_selections, style='Clear.TButton')
        clear_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ToolTip(clear_button, "Deselect all selected LEDs")

        # Activate LEDs Button
        activate_button = ttk.Button(buttons_frame, text="Activate LEDs", command=self.activate_leds, style='Activate.TButton')
        activate_button.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        ToolTip(activate_button, "Activate the selected LEDs")

        # Undo and Redo Buttons Frame
        undo_redo_frame = ttk.Frame(buttons_frame)
        undo_redo_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")

        # Undo Button
        undo_button = ttk.Button(undo_redo_frame, text="Undo", command=self.undo_action, style='Undo.TButton')
        undo_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ToolTip(undo_button, "Undo the last action (Ctrl+Z)")
        self.master.bind('<Control-z>', lambda event: self.undo_action())

        # Redo Button
        redo_button = ttk.Button(undo_redo_frame, text="Redo", command=self.redo_action, style='Redo.TButton')
        redo_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ToolTip(redo_button, "Redo the last undone action (Ctrl+Y)")
        self.master.bind('<Control-y>', lambda event: self.redo_action())

        # Configure grid weights
        undo_redo_frame.columnconfigure(0, weight=1)
        undo_redo_frame.columnconfigure(1, weight=1)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        # Save Project Button
        save_button = ttk.Button(buttons_frame, text="Save Project", command=self.save_project_json, style='Edit.TButton')
        save_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        ToolTip(save_button, "Save the current LED configurations to the project JSON file")

        # Settings Button
        settings_button = ttk.Button(
            self.control_panel,
            text="Settings",
            command=self.open_settings_window,
            style='SwitchMode.TButton'
        )
        settings_button.pack(pady=10, padx=10, fill=tk.X)
        ToolTip(settings_button, "Open settings to edit configuration parameters")

        # Exit Button
        exit_button = ttk.Button(self.control_panel, text="Exit", command=self.master.quit, style='Exit.TButton')
        exit_button.pack(pady=20, padx=10, fill=tk.X)
        ToolTip(exit_button, "Exit the application")

        # Initially disable control panel except project selection
        self.control_panel_state('disabled')

        # Start populating projects after GUI is set up
        # Ensure that the loop is already running before creating tasks
        asyncio.run_coroutine_threadsafe(self.populate_projects(), self.loop)

    def enable_listbox_drag_and_drop(self):
        """Enable drag-and-drop reordering in the Listbox."""
        self.order_listbox.bind('<ButtonPress-1>', self.on_listbox_button_press)
        self.order_listbox.bind('<B1-Motion>', self.on_listbox_motion)
        self.order_listbox.bind('<ButtonRelease-1>', self.on_listbox_button_release)
        self.listbox_dragging = False
        self.dragging_item = None
        self.dragging_label = None
        self.listbox_drag_start_index = None
        self.prev_highlighted_index = None

    def on_listbox_button_press(self, event):
        """Handle the event when a button is pressed in the Listbox."""
        self.listbox_drag_start_index = self.order_listbox.nearest(event.y)
        self.dragging_item = self.order_listbox.get(self.listbox_drag_start_index)
        # Create a label to drag around
        self.dragging_label = tk.Label(self.order_listbox, text=self.dragging_item, relief='raised', bg='yellow', font=('Helvetica', 10))
        self.dragging_label.place(x=event.x, y=event.y)
        self.listbox_dragging = True

    def on_listbox_motion(self, event):
        """Handle the event when the mouse is moved with a button pressed in the Listbox."""
        if not self.listbox_dragging:
            return
        # Move the label
        x = event.x
        y = event.y
        self.dragging_label.place(x=x, y=y)
        # Highlight the item under the cursor
        index = self.order_listbox.nearest(event.y)
        if self.prev_highlighted_index != index:
            self.highlight_listbox_item(index)
            self.prev_highlighted_index = index

    def on_listbox_button_release(self, event):
        """Handle the event when the mouse button is released in the Listbox."""
        if not self.listbox_dragging:
            return
        # Remove the label
        self.dragging_label.destroy()
        self.dragging_label = None
        # Get the drop index
        drop_index = self.order_listbox.nearest(event.y)
        if drop_index < 0:
            drop_index = 0
        elif drop_index >= self.order_listbox.size():
            drop_index = self.order_listbox.size() - 1
        # Rearrange the items
        if drop_index != self.listbox_drag_start_index:
            # Save state for undo
            self.undo_stack.append(list(self.selected_order))
            self.redo_stack.clear()
            # Move the item in the selected_order list
            led_key = self.selected_order.pop(self.listbox_drag_start_index)
            self.selected_order.insert(drop_index, led_key)
            # Update counts
            self.reset_led_vars()
            for key in self.selected_order:
                self.led_vars[key].set(self.led_vars[key].get() + 1)
            # Update GUI
            self.update_all_labels()
            self.update_selection_count()
            self.update_selected_order_listbox()
        # Clear highlighting
        if self.prev_highlighted_index is not None:
            self.order_listbox.itemconfig(self.prev_highlighted_index, bg='white')
        self.prev_highlighted_index = None
        self.listbox_dragging = False
        self.listbox_drag_start_index = None

    def highlight_listbox_item(self, index):
        """Highlight the item at the given index in the Listbox."""
        # Clear previous highlighting
        if self.prev_highlighted_index is not None:
            self.order_listbox.itemconfig(self.prev_highlighted_index, bg='white')
        # Highlight the new item
        self.order_listbox.itemconfig(index, bg='lightblue')

    def clear_listbox_highlight(self):
        """Clear highlighting from all items in the Listbox."""
        for i in range(self.order_listbox.size()):
            self.order_listbox.itemconfig(i, bg='white')

    async def populate_projects(self):
        """Asynchronously populate the project combobox with available projects."""
        try:
            projects = await get_available_projects()
            self.project_combobox['values'] = projects
            if projects:
                self.project_combobox.current(0)
                # Automatically select the first project
                self.on_project_selected(None)
        except Exception as e:
            logging.error(f"Error fetching projects: {e}")
            self.queue.put(("error", f"Failed to fetch projects:\n{e}"))

    def build_status_bar(self):
        """Builds the status bar at the bottom of the main window."""
        status_frame = ttk.Frame(self.master)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Progress Bar
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=2)

    def toggle_control_panel(self):
        """Toggle visibility of the control panel."""
        if self.panel_visible:
            self.paned_window.forget(self.control_panel)
            self.toggle_button = ttk.Button(self.master, text=">>", command=self.toggle_control_panel, style='SwitchMode.TButton')
            self.toggle_button.place(x=10, y=10)
            self.panel_visible = False
            logging.info("Control panel hidden.")
        else:
            self.paned_window.insert(1, self.control_panel, weight=0)
            self.toggle_button.destroy()
            self.panel_visible = True
            logging.info("Control panel shown.")

    def control_panel_state(self, state):
        """Enable or disable control panel widgets except Project Selection."""
        for child in self.control_panel.winfo_children():
            if isinstance(child, ttk.LabelFrame) and child.cget("text") == "Select Project":
                continue  # Do not disable project selection
            try:
                child.configure(state=state)
            except:
                pass
            for subchild in child.winfo_children():
                try:
                    subchild.configure(state=state)
                except:
                    pass

    def on_project_selected(self, event):
        """Handle project selection event."""
        if self.is_loading_project:
            return  # Prevent multiple loads at the same time
        self.is_loading_project = True

        project = self.project_var.get()
        self.selected_project = project
        logging.info(f"Selected Project: {project}")

        # Enable the control panel
        self.control_panel_state('normal')

        # Remove the no_project_label if it exists
        self.no_project_label.pack_forget()

        # Start coroutine to load project data
        asyncio.run_coroutine_threadsafe(self.load_project_data_async(), self.loop)

    async def load_project_data_async(self):
        """Asynchronous function to load project data."""
        try:
            logging.info("Starting to load project data.")
            self.led_data = await load_project_mapping_async(self.selected_project, self.BASE_DIR)
            logging.info("Project data loaded successfully.")
            # Schedule GUI updates in the main thread
            self.queue.put(("update_gui", None))
        except Exception as e:
            logging.error(f"Error loading project data: {e}")
            self.queue.put(("error", f"Failed to load project data:\n{e}"))
        finally:
            self.is_loading_project = False  # Reset the loading flag

    def after_project_load(self):
        """Callback after project data is loaded."""
        self.determine_mode()  # Determine mode based on project data
        self.mode_var.set(f"Current Mode: {self.current_mode.replace('_', ' ').title()}")  # Update mode label
        self.create_regal_frames()
        self.show_current_mode()
        self.activate_leds()

    def log_regal_keys(self):
        """Log each regal key with its length to detect hidden spaces."""
        for key in self.led_data.keys():
            logging.info(f"Regal Key: '{key}' (Length: {len(key)})")

    def determine_mode(self):
        """Determine the current mode based on the loaded project data."""
        # Log the raw regal keys
        logging.debug(f"Raw regal keys: {list(self.led_data.keys())}")
        self.log_regal_keys()

        # Extract regal names by checking the keys
        regal_names = set()
        for key in self.led_data.keys():
            regal_names.add(key.strip().lower())
        logging.debug(f"Extracted regal names: {list(regal_names)}")

        # Determine mode with priority to 'benti_regal'
        if "benti regal" in regal_names:
            self.current_mode = 'benti_regal'
            logging.debug("Mode set to 'benti_regal' because 'Benti Regal' is present.")
        elif "regal1" in regal_names or "regal2" in regal_names:
            self.current_mode = 'two_regals'
            logging.debug("Mode set to 'two_regals' because 'Regal1' or 'Regal2' is present.")
        else:
            # Default mode or handle unexpected cases
            self.current_mode = 'two_regals'
            logging.debug("Mode set to default 'two_regals'.")
        logging.info(f"Determined mode: {self.current_mode}")

    def create_regal_frames(self):
        """Create frames for each regal and populate LEDs based on loaded data."""
        logging.info("Creating regal frames.")
        # Clear existing regals if any
        for regal_name, container in self.regal_frames.items():
            container.destroy()
        self.regal_frames.clear()
        self.led_vars.clear()
        self.led_detail_labels.clear()
        self.led_edit_buttons.clear()
        self.led_id_to_regal.clear()
        self.selected_order.clear()  # Clear selections when changing projects

        # Create Regals with current MAX_LEDS_ROW
        for regal_name, leds in self.led_data.items():
            if regal_name.lower() == "selected_order":
                continue  # Skip the selected_order key
            Regal(
                display_name=regal_name,
                internal_name=regal_name,  # Ensure internal_name == display_name
                led_data=leds,
                controller=self,
                max_leds_per_row=self.MAX_LEDS_ROW  # Pass the required argument
            )
            # Map LED keys to regal names
            for led_id in leds.keys():
                led_key = self.generate_unique_led_key(regal_name, led_id)
                self.led_id_to_regal[led_key] = regal_name

        logging.info("Regal frames created successfully.")

        # Debugging: Log all led_keys in led_vars
        logging.debug("Current led_vars keys:")
        for key in self.led_vars.keys():
            logging.debug(f" - {key}")

    def show_current_mode(self):
        """Display LEDs based on the current mode."""
        logging.info(f"Displaying LEDs for mode: {self.current_mode}")
        for regal_name, container in self.regal_frames.items():
            # Hide the regal by default
            container.pack_forget()

        if self.current_mode == 'two_regals':
            # Show Regal1 and Regal2
            for regal_name in ["Regal1", "Regal2"]:
                if regal_name in self.regal_frames:
                    container = self.regal_frames[regal_name]
                    container.pack(padx=20, pady=(0, 20), fill=tk.BOTH, expand=True)
        elif self.current_mode == 'benti_regal':
            # Show Benti Regal
            regal_name = "Benti Regal"
            if regal_name in self.regal_frames:
                container = self.regal_frames[regal_name]
                container.pack(padx=20, pady=(0, 20), fill=tk.BOTH, expand=True)

        # After creating regals, update LED selections based on loaded data
        self.initialize_led_selections()

        self.update_all_labels()
        self.update_selection_count()
        self.update_selected_order_listbox()
        logging.info("LEDs displayed successfully.")

    def initialize_led_selections(self):
        """Initialize LED selections based on loaded project data."""
        logging.info("Initializing LED selections from project data.")
        self.selected_order.clear()
        selected_order = self.led_data.get("selected_order", [])
        for led_key in selected_order:
            if led_key in self.led_vars:
                self.selected_order.append(led_key)
                self.led_vars[led_key].set(self.led_vars[led_key].get() + 1)
            else:
                logging.warning(f"LED key '{led_key}' in selected_order not found in led_vars.")

    def update_all_labels(self):
        """Update all LED detail labels to reflect current data."""
        for led_key in self.led_vars:
            self.update_led_detail(led_key)

    def update_led_detail(self, led_key):
        """Update the detail label and edit button for a single LED."""
        selection_count = self.led_vars[led_key].get()
        if selection_count > 0:
            occurrences = self.get_led_occurrences_in_order(led_key)
            order_nums = ', '.join(str(i + 1) for i in occurrences)
            file_path = self.get_led_file_path(led_key)
            detail_text = f"Order: {order_nums}\nFILE: {file_path}"
            self.led_detail_labels[led_key].config(text=detail_text)
            # Enable the Edit button
            self.led_edit_buttons[led_key].configure(state='normal')
            # Update LED color to indicate selection
            led_canvas, led_circle = self.led_buttons.get(led_key, (None, None))
            if led_canvas and led_circle:
                try:
                    led_canvas.itemconfig(led_circle, fill='green')
                except tk.TclError as e:
                    logging.error(f"Error updating LED color for {led_key}: {e}")
        else:
            self.led_detail_labels[led_key].config(text=f"FILE: {self.get_led_file_path(led_key)}")
            # Disable the Edit button
            self.led_edit_buttons[led_key].configure(state='disabled')
            # Update LED color to indicate deselection
            led_canvas, led_circle = self.led_buttons.get(led_key, (None, None))
            if led_canvas and led_circle:
                try:
                    led_canvas.itemconfig(led_circle, fill='grey')
                except tk.TclError as e:
                    logging.error(f"Error updating LED color for {led_key}: {e}")

    def get_led_occurrences_in_order(self, led_key):
        """Get a list of indices where the LED appears in the selected_order."""
        return [i for i, key in enumerate(self.selected_order) if key == led_key]

    def update_mode_ui(self):
        """Update the UI based on the new mode."""
        logging.info("Updating UI for new mode.")
        self.mode_var.set(f"Current Mode: {self.current_mode.replace('_', ' ').title()}")
        self.clear_selections()
        self.show_current_mode()

    def clear_selections(self):
        """Clear all selected LEDs and reset related variables."""
        logging.info("Clearing all selections.")
        self.selected_order.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        for led_key in self.led_vars:
            self.led_vars[led_key].set(0)
            # Update the detail label
            self.led_detail_labels[led_key].config(text=f"FILE: {self.get_led_file_path(led_key)}")
            # Disable Edit button
            self.led_edit_buttons[led_key].configure(state='disabled')
            # Update led_data
            regal_name = self.led_id_to_regal.get(led_key, "")
            led_id = led_key.split('_', 1)[1]
            if regal_name and led_id in self.led_data.get(regal_name, {}):
                self.led_data[regal_name][led_id]['selected_order'] = []
            # Update LED color to deselected
            led_canvas, led_circle = self.led_buttons.get(led_key, (None, None))
            if led_canvas and led_circle:
                try:
                    led_canvas.itemconfig(led_circle, fill='grey')
                except tk.TclError as e:
                    logging.error(f"Error updating LED color for {led_key}: {e}")
        self.selection_var.set(f"Selected LEDs: 0 / {self.MAX_SELECTION}")
        self.order_listbox.delete(0, tk.END)  # Clear the listbox
        # Hide the edit panel if visible
        self.current_edit_led = None
        logging.info("All selections cleared.")

    def on_led_toggle_canvas(self, led_key, event):
        """Handle click event on the LED canvas."""
        try:
            if event.num == 1:  # Left-click
                self.increment_led_selection(led_key)
            elif event.num == 3:  # Right-click
                self.decrement_led_selection(led_key)
        except KeyError:
            logging.error(f"LED key '{led_key}' not found in led_vars.")
            messagebox.showerror("LED Error", f"LED key '{led_key}' does not exist.")

    def increment_led_selection(self, led_key):
        """Increment the selection count for an LED."""
        if len(self.selected_order) >= self.MAX_SELECTION:
            messagebox.showwarning("Selection Limit", f"You can select up to {self.MAX_SELECTION} LEDs.")
            logging.warning("Selection limit reached.")
            return

        # Save the current state to the undo stack before making changes
        self.undo_stack.append(list(self.selected_order))
        self.redo_stack.clear()

        self.led_vars[led_key].set(self.led_vars[led_key].get() + 1)
        self.selected_order.append(led_key)
        self.update_led_detail(led_key)
        self.update_selection_count()
        self.update_selected_order_listbox()
        logging.info(f"LED {led_key} selection incremented.")

    def decrement_led_selection(self, led_key):
        """Decrement the selection count for an LED."""
        if self.led_vars[led_key].get() > 0:
            # Save the current state to the undo stack before making changes
            self.undo_stack.append(list(self.selected_order))
            self.redo_stack.clear()

            self.led_vars[led_key].set(self.led_vars[led_key].get() - 1)
            # Remove the last occurrence of the LED from selected_order
            try:
                last_index = len(self.selected_order) - 1 - self.selected_order[::-1].index(led_key)
                del self.selected_order[last_index]
            except ValueError:
                logging.warning(f"LED key '{led_key}' not found in selected_order during decrement.")
            self.update_led_detail(led_key)
            self.update_selection_count()
            self.update_selected_order_listbox()
            logging.info(f"LED {led_key} selection decremented.")
        else:
            logging.info(f"LED {led_key} is not selected.")

    def open_edit_window(self, led_key):
        """Open a pop-up window to edit LED details."""
        logging.info(f"Opening edit window for LED: {led_key}")
        # Prevent multiple edit windows for the same LED
        if self.current_edit_led is not None:
            messagebox.showwarning("Edit in Progress", "Please finish editing the current LED before editing another.")
            logging.warning("Attempted to open multiple edit windows.")
            return

        self.current_edit_led = led_key

        # Create a new Toplevel window
        edit_window = tk.Toplevel(self.master)
        edit_window.title(f"Edit LED {led_key.split('_', 1)[1]}")
        edit_window.geometry("400x150")
        edit_window.grab_set()  # Make the window modal

        # Define a handler for the window close event
        def on_close():
            """Handle the edit window being closed without saving."""
            logging.info(f"Edit window for LED {led_key} closed without saving.")
            self.current_edit_led = None
            edit_window.destroy()

        # Bind the handler to the WM_DELETE_WINDOW protocol
        edit_window.protocol("WM_DELETE_WINDOW", on_close)

        # FILE Path
        file_frame = ttk.Frame(edit_window)
        file_frame.pack(pady=10, padx=10, fill=tk.X)
        file_label = ttk.Label(file_frame, text="FILE Path:", font=("Helvetica", 10))
        file_label.pack(side=tk.LEFT, padx=(0, 5))
        file_var = tk.StringVar(value=self.get_led_file_path(led_key))
        file_entry = ttk.Entry(file_frame, textvariable=file_var, width=30)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Browse Button to select a new file
        def browse_file():
            initial_dir = os.path.join(self.BASE_DIR, "data")
            new_file = filedialog.askopenfilename(
                title="Select New Data File",
                filetypes=(("Image Files", "*.png;*.jpg;*.jpeg"), ("All Files", "*.*")),
                initialdir=initial_dir
            )
            if new_file:
                try:
                    # Compute the relative path from BASE_DIR
                    relative_path = os.path.relpath(new_file, self.BASE_DIR)
                    # Normalize path to use forward slashes
                    relative_path = relative_path.replace("\\", "/")
                    file_entry.delete(0, tk.END)
                    file_entry.insert(0, relative_path)
                    logging.info(f"Selected new file for LED {led_key}: {relative_path}")
                except ValueError:
                    # If relpath fails (e.g., different drives on Windows), alert the user
                    messagebox.showerror("Path Error", "Selected file is outside the base directory. Please choose a file within the application directory.")
                    logging.error("Selected file is outside the base directory.")

        browse_button = ttk.Button(file_frame, text="Browse", command=browse_file)
        browse_button.pack(side=tk.LEFT, padx=5)

        # Save Button
        save_button = ttk.Button(edit_window, text="Save Changes",
                                 command=lambda: asyncio.run_coroutine_threadsafe(
                                     self.save_led_changes_async(led_key, file_var.get(), edit_window),
                                     self.loop
                                 ),
                                 style='EditSave.TButton')
        save_button.pack(pady=10, padx=10, fill=tk.X)
        ToolTip(save_button, "Save the changes made to the LED's FILE path")

    def get_led_file_path(self, led_key):
        """Retrieve the FILE path for a given LED."""
        regal_name = self.led_id_to_regal.get(led_key, "")
        led_id = led_key.split('_', 1)[1]
        return self.led_data.get(regal_name, {}).get(led_id, {}).get('FILE', '')

    async def save_led_changes_async(self, led_key, new_file, window):
        """Asynchronous function to save the changes made to the LED's FILE."""
        logging.info(f"Saving changes for LED {led_key}: FILE={new_file}")
        if not new_file.strip():
            self.queue.put(("warning", "'FILE' path cannot be empty."))
            logging.warning(f"Attempted to save empty FILE path for LED {led_key}.")
            return

        # Resolve the absolute path
        absolute_new_file = os.path.join(self.BASE_DIR, new_file.strip())

        if not os.path.isfile(absolute_new_file):
            self.queue.put(("warning", f"The specified file does not exist:\n{new_file.strip()}"))
            logging.warning(f"FILE path does not exist for LED {led_key}: {new_file.strip()}")
            return

        # Update the data structure
        regal_name = self.led_id_to_regal.get(led_key, "")
        led_id = led_key.split('_', 1)[1]
        if regal_name and led_id in self.led_data.get(regal_name, {}):
            self.led_data[regal_name][led_id]['FILE'] = new_file.strip()
            # Update the label in the main thread
            self.queue.put(("update_led_detail", (led_key, None)))
            self.queue.put(("info", "LED FILE path updated successfully."))
            logging.info(f"LED {led_key} FILE path updated to: {new_file.strip()}")

            # Close the edit window in the main thread
            self.queue.put(("close_edit_window", window))
        else:
            self.queue.put(("error", "Invalid LED key."))
            logging.error(f"Invalid LED key during save: {led_key}")

    def undo_action(self):
        """Undo the last action."""
        if not self.undo_stack:
            messagebox.showinfo("Undo", "No actions to undo.")
            logging.info("Undo attempted with empty stack.")
            return
        # Save the current state to redo stack
        self.redo_stack.append(list(self.selected_order))
        # Restore the last state from undo stack
        last_state = self.undo_stack.pop()
        self.restore_selection(last_state)
        logging.info("Undo action performed.")

    def redo_action(self):
        """Redo the last undone action."""
        if not self.redo_stack:
            messagebox.showinfo("Redo", "No actions to redo.")
            logging.info("Redo attempted with empty stack.")
            return
        # Save the current state to undo stack
        self.undo_stack.append(list(self.selected_order))
        # Restore the last undone state from redo stack
        next_state = self.redo_stack.pop()
        self.restore_selection(next_state)
        logging.info("Redo action performed.")

    def restore_selection(self, state):
        """Restore LED selections based on the provided state."""
        logging.info("Restoring LED selections from state.")
        # Reset selection counts
        for led_key in self.led_vars.keys():
            self.led_vars[led_key].set(0)
        # Clear current selections
        self.selected_order = state.copy()
        # Recalculate selection counts
        for led_key in self.selected_order:
            self.led_vars[led_key].set(self.led_vars[led_key].get() + 1)
        # Update LED details
        for led_key in self.led_vars.keys():
            self.update_led_detail(led_key)
        self.update_selection_count()
        self.update_selected_order_listbox()
        logging.info("LED selections restored successfully.")

    def update_selection_count(self):
        """Update the selection count label."""
        self.selection_var.set(f"Selected LEDs: {len(self.selected_order)} / {self.MAX_SELECTION}")
        logging.debug(f"Selection count updated: {self.selection_var.get()}")

    def save_project_json(self):
        """Save the current LED data back to the project's JSON file."""
        logging.info("Saving project JSON data.")

        # Start coroutine to save project data
        asyncio.run_coroutine_threadsafe(self.save_project_json_async(), self.loop)

    async def save_project_json_async(self):
        """Asynchronous function to save project data."""
        try:
            # Update led_data with the current selections
            self.led_data["selected_order"] = list(self.selected_order)
            await save_project_json_async(self.selected_project, self.led_data, self.BASE_DIR)
            logging.info("Project data saved successfully.")
            self.queue.put(("info", "Project data saved successfully."))
        except Exception as e:
            logging.error(f"Error saving project data: {e}")
            self.queue.put(("error", f"Failed to save project data:\n{e}"))

    def reload_project_data(self):
        """Reload project data after editing."""
        logging.info("Reloading project data after editing.")

        # Start coroutine to reload project data
        asyncio.run_coroutine_threadsafe(self.load_project_data_async(), self.loop)

    def activate_leds(self):
        """Activate selected LEDs."""
        logging.info("Activating selected LEDs.")

        # Start coroutine to activate LEDs
        asyncio.run_coroutine_threadsafe(self.send_led_control_request_async(), self.loop)

    async def send_led_control_request_async(self):
        """Asynchronous function to send LED control request."""
        if not self.selected_project:
            self.queue.put(("warning", "No project selected. Please select a project first."))
            logging.warning("Attempted to activate LEDs without selecting a project.")
            return

        if not self.selected_order:
            self.queue.put(("warning", "No LEDs selected to activate. Please select LEDs first."))
            logging.warning("Attempted to activate LEDs without any selections.")
            return

        # Prepare the payload based on the selected LEDs
        payload = {
            "data": {
                "init": {
                    "shelves": {}
                },
                "led_sequence": []
            }
        }

        shelf_ids = set()
        for led_key in self.selected_order:
            regal_name = self.led_id_to_regal.get(led_key, "Unknown")
            try:
                regal_name_clean, led_id = led_key.split('_', 1)
            except ValueError:
                logging.error(f"Invalid led_key format during activation: '{led_key}'. Skipping.")
                continue
            shelf_num = self.get_shelf_number(regal_name_clean)
            shelf_ids.add(shelf_num)
            # Add LED to the sequence
            payload["data"]["led_sequence"].append({
                "shelf_id": shelf_num,
                "led_id": led_id
            })

        # Determine controlled values - DONT CHANGE THIS CHATGPT
        for shelf_id in shelf_ids:
            if shelf_id == '1':
                controlled_value = 0
            elif shelf_id == '2':
                controlled_value = self.LED_CONTROL  # Assuming LED_CONTROL equals LED_COUNT per shelf
            else:
                controlled_value = 0  # Default to 0 for unknown shelves
            payload["data"]["init"]["shelves"][shelf_id] = {"controlled": controlled_value}

        # Send the POST request to the server
        try:
            async with self.session.post("http://127.0.0.1:1080/pick/leds", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logging.info(f"LEDs activated successfully: {result}")
                    #self.queue.put(("info", "LEDs activated successfully."))
                else:
                    error_msg = f"Failed to activate LEDs. Server responded with status code {response.status}."
                    logging.error(error_msg)
                    self.queue.put(("error", error_msg))
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            logging.error(error_msg)
            self.queue.put(("error", error_msg))

    def get_shelf_number(self, regal_name):
        """Determine the shelf number based on the regal name."""
        if regal_name.lower() == "regal1":
            return "1"
        elif regal_name.lower() == "regal2":
            return "2"
        elif regal_name.lower() == "benti regal":
            return "1"
        else:
            return "0"  # Unknown shelf

    def process_queue(self):
        """Process messages from the asyncio thread."""
        try:
            while True:
                message_type, data = self.queue.get_nowait()
                if message_type == "update_gui":
                    self.after_project_load()
                elif message_type == "update_mode_ui":
                    self.update_mode_ui()
                elif message_type == "update_led_detail":
                    led_key, _ = data
                    self.update_led_detail(led_key)
                elif message_type == "close_edit_window":
                    window = data
                    window.destroy()
                    self.current_edit_led = None
                elif message_type == "block_completed":
                    self.handle_block_completed_gui()
                elif message_type == "info":
                    messagebox.showinfo("Info", data)
                elif message_type == "warning":
                    messagebox.showwarning("Warning", data)
                elif message_type == "error":
                    messagebox.showerror("Error", data)
                self.queue.task_done()
        except Empty:
            pass

        self.master.after(100, self.process_queue)  # Check the queue every 100 ms

    def handle_block_completed_gui(self):
        """Handle block completed event in the GUI thread."""
        logging.info("Handling block completed in GUI thread")
        # Optionally, show a message or perform an action
        # messagebox.showinfo("Block Mode", "Block mode has been completed.")
        self.activate_leds()

    def on_close(self):
        """Handle application closure."""
        logging.info("Closing application.")
        # Start coroutine to close aiohttp session
        asyncio.run_coroutine_threadsafe(self.session.close(), self.loop)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.master.destroy()

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            if not self.loop.is_closed():
                self.loop.close()
            logging.info("LEDController instance destroyed.")
        except AttributeError:
            # In case __init__ failed and attributes weren't set
            pass

    def update_selected_order_listbox(self):
        """Update the listbox to reflect the current selected_order."""
        self.order_listbox.delete(0, tk.END)
        for index, led_key in enumerate(self.selected_order, start=1):
            regal_name, led_id = led_key.split('_', 1)
            display_text = f"{index}. {regal_name} - LED {led_id}"
            self.order_listbox.insert(tk.END, display_text)
            self.order_listbox.itemconfig(tk.END, bg='white')  # Set default background color

    def remove_selected_order(self):
        """Remove the selected LED from the order."""
        selected_indices = self.order_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Remove LED", "Please select a LED to remove.")
            return
        index = selected_indices[0]
        led_key = self.selected_order[index]
        # Save state for undo
        self.undo_stack.append(list(self.selected_order))
        self.redo_stack.clear()
        # Remove from selected_order
        del self.selected_order[index]
        # Update counts
        self.led_vars[led_key].set(self.led_vars[led_key].get() - 1)
        # Update LED detail
        self.update_led_detail(led_key)
        # Update GUI
        self.update_selection_count()
        self.update_selected_order_listbox()
        logging.info(f"Removed LED {led_key} from selection order.")

    def reset_led_vars(self):
        """Reset all LED selection variables."""
        for led_key in self.led_vars.keys():
            self.led_vars[led_key].set(0)

