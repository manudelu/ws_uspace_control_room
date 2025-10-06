import os
import asyncio
import websockets
import json
import paho.mqtt.client as mqtt
from dotenv import load_dotenv 

load_dotenv()
 
# ---------------- MQTT CONFIG ----------------
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost') 
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883)) 
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
MQTT_TOPIC = "fleet/+/telemetry"  # + = wildcard for any drone

# ---------------- WEBSOCKET CONFIG ----------------
WS_HOST = "0.0.0.0"
WS_PORT = 9000
clients = set()

# Create asyncio event loop
loop = asyncio.get_event_loop()

# ---------------- MQTT CALLBACKS ----------------
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with code {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"[MQTT] Subscribed to: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        
        # Extract drone ID from topic (e.g., fleet/drone2/telemetry -> drone2)
        topic_parts = msg.topic.split("/")
        drone_topic_id = topic_parts[1]
        data["drone_topic_id"] = drone_topic_id

        # Broadcast JSON to all WebSocket clients
        asyncio.run_coroutine_threadsafe(broadcast(json.dumps(data)), loop)

        #print(f"[MQTT] Received from {drone_topic_id}: {payload}")
    except Exception as e:
        print(f"[ERROR] Failed to process MQTT message: {e}")

# ---------------- WEBSOCKET SERVER ----------------
async def sensor_server(websocket):
    clients.add(websocket)
    print(f"[WS] Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            pass  
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.remove(websocket)
        print(f"[WS] Client disconnected: {websocket.remote_address}")

async def broadcast(message):
    if clients:
        await asyncio.gather(*(client.send(message) for client in clients))

async def main():
    async with websockets.serve(sensor_server, WS_HOST, WS_PORT):
        print(f"[WS] WebSocket server started at ws://{WS_HOST}:{WS_PORT}")
        await asyncio.Future()  

# ---------------- MQTT CLIENT SETUP ----------------
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()  

# ---------------- RUN WEBSOCKET SERVER ----------------
if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n[INFO] Bridge stopped manually")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()