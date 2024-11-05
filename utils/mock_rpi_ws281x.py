# utils/mock_rpi_ws281x.py

class Color:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b

class Adafruit_NeoPixel:
    def __init__(self, *args, **kwargs):
        pass

    def begin(self):
        print("Mock NeoPixel initialized.")

    def setPixelColor(self, pixel, color):
        print(f"Mock setPixelColor: Pixel {pixel} set to color ({color.r}, {color.g}, {color.b}).")

    def show(self):
        print("Mock show called.")
