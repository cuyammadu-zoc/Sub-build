import socket
import json
import time
import math

# Network Setup (Listens on localhost)
SIM_IP = "127.0.0.1"
SIM_PORT = 8888

class VirtualSubmarine:
    def __init__(self):
        # Physics State
        self.depth = 0.5        # Meters underwater
        self.heading = 0.0      # Degrees (0-360)
        self.pitch = 0.0        # Degrees (-90 to 90)
        self.temp = 18.5        # Water temp (°C)
        
        # Virtual Thruster PWM States (1000 to 2000)
        self.pwms = {"fl": 1500, "fr": 1500, "bl": 1500, "br": 1500}
        
    def update_physics(self, dt: float):
        """Simulates water drag, differential thrust, and buoyancy."""
        # Convert PWM (1100-1900) to thrust ratio (-1.0 to +1.0)
        t_fl = (self.pwms["fl"] - 1500) / 400.0
        t_fr = (self.pwms["fr"] - 1500) / 400.0
        t_bl = (self.pwms["bl"] - 1500) / 400.0
        t_br = (self.pwms["br"] - 1500) / 400.0

        # Yaw (Turning): Differential thrust between left and right motors
        yaw_rate = ((t_fl + t_bl) - (t_fr + t_br)) * 30.0  # Deg/sec
        self.heading = (self.heading + yaw_rate * dt) % 360.0

        # Pitch (Angle): Differential thrust between front and rear motors
        self.pitch += ((t_fl + t_fr) - (t_bl + t_br)) * 10.0 * dt
        self.pitch = max(-45.0, min(45.0, self.pitch))

        # Forward Motion & Depth change
        forward_thrust = (t_fl + t_fr + t_bl + t_br) / 4.0
        self.depth += math.sin(math.radians(self.pitch)) * forward_thrust * dt
        self.depth = max(0.0, self.depth) # Cannot go above surface

    def get_imu_telemetry(self) -> dict:
        """Simulates MPU6050 accelerometer output."""
        return {
            "ax": round(math.sin(math.radians(self.pitch)), 2),
            "ay": round(math.sin(math.radians(self.heading)), 2),
            "az": 9.81, # Gravity vector
            "depth": round(self.depth, 2),
            "heading": round(self.heading, 1),
            "temp": self.temp
        }

def run_simulation():
    sub = VirtualSubmarine()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SIM_IP, SIM_PORT))
    sock.setblocking(False)
    
    print(f"[SIMULATOR] Virtual Submarine running on {SIM_IP}:{SIM_PORT}")
    last_time = time.time()

    while True:
        now = time.time()
        dt = now - last_time
        last_time = now

        # 1. Listen for thrust commands from ground control
        try:
            data, addr = sock.recvfrom(256)
            packet = json.loads(data.decode('utf-8'))
            if all(k in packet for k in ("fl", "fr", "bl", "br")):
                sub.pwms = packet
        except (BlockingIOError, json.JSONDecodeError):
            pass  # No packet received this frame

        # 2. Physics step
        sub.update_physics(dt)

        # 3. Print HUD Diagnostics to console
        telem = sub.get_imu_telemetry()
        print(f"\r[SUB HUD] Depth: {telem['depth']}m | Heading: {telem['heading']}° | Pitch: {sub.pitch:.1f}° | Motors: {list(sub.pwms.values())}", end="")

        time.sleep(0.05) # 20Hz Simulation Loop

if __name__ == "__main__":
    run_simulation()
