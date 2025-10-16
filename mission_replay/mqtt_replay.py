import os, time, argparse, json, paho.mqtt.client as mqtt
import pandas as pd
from dotenv import load_dotenv

def compose_message(ts: float, lat: float, lon: float, alt: float, vx: float, vy: float, vz: float) -> str:
    message = {
        "avoidance": {
            "back": 0.0, "backHealth": 0,
            "down": 0.0, "downHealth": 0,
            "front": 0.0, "frontHealth": 0,
            "left": 0.0, "leftHealth": 0,
            "reserved": 0,
            "right": 0.0, "rightHealth": 0,
            "up": 0.0, "upHealth": 0
        },
        "battery": {"capacity": 0, "current": 0, "percentage": 0, "voltage": 0},
        "drone": {"id": 1, "type": "REPLAY"},
        "extPosition": {"altitude": 0.0, "latitude": 0.0, "longitude": 0.0, "status": 0.0},
        "gpsDetail": {
            "GPScounter": 0, "NSV": 0, "fix": 0.0,
            "hacc": 0.0, "hdop": 0.0, "pdop": 0.0,
            "sacc": 0.0, "usedGLN": 0, "usedGPS": 0, "vacc": 0.0
        },
        "position": {
            "altitude": 0.0,
            "height": alt,
            "latitude": lat,
            "latitudeRad": 0.0,
            "longitude": lon,
            "longitudeRad": 0.0
        },
        "quaternion": {"q0": 0.0, "q1": 0.0, "q2": 0.0, "q3": 0.0},
        "rc": {"gear": 0, "mode": 0, "pitch": 0, "roll": 0, "throttle": 0, "yaw": 0},
        "status": {"error": 0, "flight": 1, "gear": 0, "mode": 0},
        "timestamp": ts,
        "velocity": {"x": vx, "y": vy, "z": vz},
        "angularVelocity": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    return json.dumps(message)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected to broker")
    else:
        raise ConnectionError(f"[MQTT] Connection failed: {rc}")

def main():
    parser = argparse.ArgumentParser(description="Replay CSV over MQTT")
    parser.add_argument("--file", "-f", default="log_10Hz_vel.csv", help="CSV file path")
    parser.add_argument("--drone_id", "-i", type=int, default=2)
    parser.add_argument("--broker", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    load_dotenv()
    broker = args.broker or os.getenv("MQTT_BROKER")
    port = args.port or int(os.getenv("MQTT_PORT", 1883))
    user = args.user or os.getenv("MQTT_USERNAME")
    password = args.password or os.getenv("MQTT_PASSWORD")

    df = pd.read_csv(args.file)

    client = mqtt.Client()
    client.username_pw_set(user, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    client.loop_start()

    topic = f"fleet/drone{args.drone_id}/telemetry"
    time.sleep(0.5)

    for idx, row in df.iterrows():
        msg = compose_message(*row[["timestamp","latitude","longitude","altitude","vx","vy","vz"]])
        ret = client.publish(topic, msg)
        if ret.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Failed to publish at index {idx}")
        else:
            print(f"[MQTT] Published {idx} -> {row['latitude']}, {row['longitude']}, {row['altitude']}")
        if idx < len(df) - 1:
            sleep_time = row.get("dt", 0.1)
            time.sleep(sleep_time)

if __name__ == "__main__":
    main()
