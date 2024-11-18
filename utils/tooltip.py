# utils/tooltip.py

import tkinter as tk
from tkinter import ttk

class ToolTip:
    """Class to create tooltips for widgets."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip or not self.text:
            return
        x = y = 0
        # Adjust tooltip position based on widget
        if hasattr(self.widget, 'winfo_rootx'):
            x = self.widget.winfo_rootx() + 25
            y = self.widget.winfo_rooty() + 20
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tooltip,
            text=self.text,
            justify='left',
            background="#ffffe0",
            relief='solid',
            borderwidth=1,
            font=("Helvetica", "10", "normal")
        )
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
