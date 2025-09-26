import json
import math
import csv
import os

# Earth radius in meters
R = 6378137  

def latlon_to_local_xy(lat0, lon0, lat, lon):
    """Convert lat/lon to local tangent plane (meters) using equirectangular approximation."""
    dlat = math.radians(lat - lat0)
    dlon = math.radians(lon - lon0)
    x = R * dlon * math.cos(math.radians((lat + lat0) / 2))  # East
    y = R * dlat                                             # North
    return x, y

def read_csv_positions(filename):
    """Read CSV with headers lat,lon,alt (alt optional, default 0)."""
    positions = []
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            lat = float(row['lat'])
            lon = float(row['lon'])
            alt = float(row['alt']) if 'alt' in row and row['alt'] else 0
            positions.append((lat, lon, alt))
    return positions

def generate_vehicle_entry(index, x, y, z, lat=None, lon=None):
    """Create a vehicle entry following your exact AirSim format."""
    vehicle = {
        "VehicleType": "PX4Multirotor",
        "UseSerial": False,
        "LockStep": True,
        "UseTcp": True,
        "TcpPort": 4560 + index,
        "ControlPortLocal": 14540 + index,
        "ControlPortRemote": 14580 + index,
        "LocalHostIp": "0.0.0.0",
        "X": x,
        "Y": y,
        "Z": z,
        "Yaw": 0,
        "Sensors": {
            "Barometer": {
                "SensorType": 1,
                "Enabled": True,
                "PressureFactorSigma": 0.0001825
            }
        },
        "Parameters": {
            "NAV_RCL_ACT": 0,
            "NAV_DLL_ACT": 0,
            "COM_OBL_ACT": 1
        }
    }
    # Add LPE_LAT/LON only for the first drone
    if lat is not None and lon is not None:
        vehicle["Parameters"]["LPE_LAT"] = lat
        vehicle["Parameters"]["LPE_LON"] = lon
    return vehicle

def update_settings(settings_file, positions):
    """Update existing settings.json with drones from CSV."""
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            settings = json.load(f)
    else:
        raise FileNotFoundError(f"{settings_file} not found!")

    if not positions:
        raise ValueError("No drone positions provided!")

    # First drone is the origin
    lat0, lon0, alt0 = positions[0]
    settings["OriginGeopoint"] = {
        "Latitude": lat0,
        "Longitude": lon0,
        "Altitude": 0
    }

    # Clear old vehicles
    settings["Vehicles"] = {}

    # Add new drones
    for i, (lat, lon, alt) in enumerate(positions):
        x_disp, y_disp = latlon_to_local_xy(lat0, lon0, lat, lon)

        # Swap X/Y: X = North, Y = East
        x = y_disp
        y = x_disp

        # Z relative to sea level (first drone altitude as reference)
        z = -(alt - alt0)

        # Only first drone has LPE_LAT/LON
        lat_param = lat if i == 0 else None
        lon_param = lon if i == 0 else None

        settings["Vehicles"][f"Drone{i+1}"] = generate_vehicle_entry(i, x, y, z, lat_param, lon_param)

    # Save back to file
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

    print(f"Updated {settings_file} with {len(positions)} drones.")

if __name__ == "__main__":
    positions = read_csv_positions("drones.csv")
    update_settings("settings.json", positions)