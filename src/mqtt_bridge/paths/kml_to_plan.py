import xml.etree.ElementTree as ET
import json

# Load the KML file (relative path from the script's location)
kml_file = 'PathB.kml'
tree = ET.parse(kml_file)
root = tree.getroot()

# Namespace for KML
ns = {'kml': 'http://www.opengis.net/kml/2.2'}

# Extract coordinates
coordinates = []
for placemark in root.findall('.//kml:Placemark', ns):
    for line_string in placemark.findall('.//kml:LineString/kml:coordinates', ns):
        coords = line_string.text.strip().split()
        for coord in coords:
            parts = coord.split(',')
            lon = float(parts[0])
            lat = float(parts[1])
            alt = float(parts[2]) if len(parts) > 2 else 10  # Default altitude to 10 meters if missing
            coordinates.append((lat, lon, alt))

# Create the .plan file structure
plan = {
    "fileType": "Plan",
    "geoFence": {
        "circles": [],
        "polygons": [],
        "version": 2
    },
    "groundStation": "QGroundControl",
    "mission": {
        "cruiseSpeed": 15,
        "firmwareType": 12,
        "hoverSpeed": 5,
        "items": [],
        "plannedHomePosition": [coordinates[0][0], coordinates[0][1], coordinates[0][2]],
        "vehicleType": 2,
        "version": 2
    },
    "rallyPoints": {
        "points": [],
        "version": 2
    },
    "version": 1
}

# Add waypoints to the mission
for i, (lat, lon, alt) in enumerate(coordinates):
    if i == 0:
        # First item is Takeoff
        waypoint = {
            "AMSLAltAboveTerrain": None,
            "Altitude": alt,
            "AltitudeMode": 1,
            "autoContinue": True,
            "command": 22,  # 22 = Takeoff
            "doJumpId": i + 1,
            "frame": 3,
            "params": [15, 0, 0, None, lat, lon, alt],
            "type": "SimpleItem"
        }
    else:
        # Subsequent items are Waypoints
        waypoint = {
            "AMSLAltAboveTerrain": None,
            "Altitude": alt,
            "AltitudeMode": 1,
            "autoContinue": True,
            "command": 16,  # 16 = Waypoint
            "doJumpId": i + 1,
            "frame": 3,
            "params": [15, 0, 0, None, lat, lon, alt],
            "type": "SimpleItem"
        }
    plan["mission"]["items"].append(waypoint)

# Save the .plan file
plan_file = 'mission.plan'
with open(plan_file, 'w') as f:
    json.dump(plan, f, indent=4)

print(f"Generated {plan_file} successfully!")