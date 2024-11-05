import json
import os

# Define the LED layout for a single Regal
LED_LAYOUT_REGAL = [
    [54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68],
    [53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39],
    [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38],
    [23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9],
    [1, 2, 3, 4, 5, 6, 7, 8]
]

def flatten_layout(regal_layout):
    """
    Flattens a nested list of LED IDs into a single list.
    """
    return [led_id for row in regal_layout for led_id in row]

def generate_default_project(regal_layout):
    """
    Generates a default project JSON structure with 'FILE', 'selected', and 'order' fields for one regal.
    """
    # Flatten the layout
    regal_leds = flatten_layout(regal_layout)

    # Initialize the final JSON structure
    final_json = {}

    # Process the Regal
    regal_dict = {}
    for led_id in regal_leds:
        regal_dict[str(led_id)] = {
            "FILE": "data/file.png",
            "selected": False,
            "order": None
        }
    final_json["Regal"] = regal_dict

    # Optionally, you can set some LEDs as selected by default
    # For example, select the first LED
    first_led_id = str(regal_leds[0])
    final_json["Regal"][first_led_id]["selected"] = True
    final_json["Regal"][first_led_id]["order"] = 1

    return final_json

def main():
    # Generate the default project JSON structure
    default_project = generate_default_project(LED_LAYOUT_REGAL)

    # Specify the output JSON file name
    output_file = "project2.json"

    # Write the JSON structure to the file
    with open(output_file, 'w', encoding='utf-8') as json_file:
        json.dump(default_project, json_file, indent=4, ensure_ascii=False)

    print(f"Default project has been successfully written to '{output_file}'.")

if __name__ == "__main__":
    main()
