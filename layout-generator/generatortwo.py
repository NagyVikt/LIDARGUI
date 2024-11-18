import json
import os

LED_LAYOUT_REGAL1 = [
    [132, 131, 130, 129, 128, 127, 126, 125, 124, 123, 122, 121, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111],  # Row 6
    [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110],  # Row 5
    [88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67],  # Row 4
    [45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66],  # Row 3
    [44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 24, 23],  # Row 2
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]  # Row 1
]

LED_LAYOUT_REGAL2 = [
    [274, 273, 272, 271, 270, 269, 268, 267, 266, 265, 264, 263, 262, 261, 260, 259, 258, 257, 256, 255, 254, 253],  # Row 6
    [231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252],  # Row 5
    [230, 229, 228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213, 212, 211, 210, 209],  # Row 4
    [178, 179, 180, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208],  # Row 3
    [177, 176, 175, 174, 173, 172, 171, 170, 169, 168, 167, 166, 165, 164, 163, 162, 161, 160, 159, 158, 157, 156],  # Row 2
    [134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155]  # Row 1
]


def flatten_layout(regal_layout):
    """
    Flattens a nested list of LED IDs into a single list.
    """
    return [led_id for row in regal_layout for led_id in row]

def generate_default_project(regal1_layout, regal2_layout):
    """
    Generates a default project JSON structure with 'FILE', 'selected', and 'order' fields.
    """
    # Flatten the layouts
    regal1_leds = flatten_layout(regal1_layout)
    regal2_leds = flatten_layout(regal2_layout)

    # Initialize the final JSON structure
    final_json = {}

    # Process Regal1
    regal1_dict = {}
    for led_id in regal1_leds:
        regal1_dict[str(led_id)] = {
            "FILE": "data/file.png",
            "selected": False,
            "order": None
        }
    final_json["Regal1"] = regal1_dict

    # Process Regal2
    regal2_dict = {}
    for led_id in regal2_leds:
        regal2_dict[str(led_id)] = {
            "FILE": "data/file.jpg",
            "selected": False,
            "order": None
        }
    final_json["Regal2"] = regal2_dict

    # Optionally, you can set some LEDs as selected by default
    # For example, select the first LED of each regal
    final_json["Regal1"][str(regal1_leds[0])]["selected"] = True
    final_json["Regal1"][str(regal1_leds[0])]["order"] = 1

    final_json["Regal2"][str(regal2_leds[0])]["selected"] = True
    final_json["Regal2"][str(regal2_leds[0])]["order"] = 2

    return final_json

def main():
    # Generate the default project JSON structure
    default_project = generate_default_project(LED_LAYOUT_REGAL1, LED_LAYOUT_REGAL2)

    # Specify the output JSON file name
    output_file = "default_project.json"

    # Write the JSON structure to the file
    with open(output_file, 'w', encoding='utf-8') as json_file:
        json.dump(default_project, json_file, indent=4, ensure_ascii=False)

    print(f"Default project has been successfully written to '{output_file}'.")

if __name__ == "__main__":
    main()
