import socket
import json
import time
import math

SIM_IP = "127.0.0.1"
SIM_PORT = 8888

class VirtualSubmarine:
    def __init__(self):
        # Physics State
        self.depth = 0.5        # Meters underwater
        self.target_depth = 0.5 # Target depth for PID hold
        self.heading = 0.0      # Degrees (0-360)
        self.pitch = 0.0        # Degrees (-90 to 90)
        self.temp = 18.5        # Water temp (°C)
        self.mode = 0           # 0: MANUAL, 1: DEPTH_HOLD, 2: EMERGENCY_SURFACE
        
        # Virtual Thruster PWM States (1100 to 1900)
        self.pwms = {"fl": 1500, "fr": 1500, "bl": 1500, "br": 1500}
        self.last_packet_time = time.time()
        
    def update_physics(self, dt: float):
        now = time.time()
        
        # Failsafe: Emergency surface if connection drops > 2.0s
        if now - self.last_packet_time > 2.0:
            self.mode = 2  # EMERGENCY_SURFACE

        if self.mode == 2:  # EMERGENCY_SURFACE
            # Ascend to surface at 0.5 m/s rate
            self.depth = max(0.0, self.depth - (0.5 * dt))
            return

        # Convert PWM (1100-1900) to thrust ratio (-1.0 to +1.0)
        t_fl = (self.pwms["fl"] - 1500) / 400.0
        t_fr = (self.pwms["fr"] - 1500) / 400.0
        t_bl = (self.pwms["bl"] - 1500) / 400.0
        t_br = (self.pwms["br"] - 1500) / 400.0

        if self.mode == 1:  # DEPTH_HOLD PID Simulation
            error = self.target_depth - self.depth
            vertical_thrust = error * 0.8  # Simulated closed-loop PID response
            self.depth += vertical_thrust * dt
        else:  # MANUAL MODE
            forward_thrust = (t_fl + t_fr + t_bl + t_br) / 4.0
            self.depth += math.sin(math.radians(self.pitch)) * forward_thrust * dt

        self.depth = max(0.0, self.depth)

        # Yaw & Pitch dynamics
        yaw_rate = ((t_fl + t_bl) - (t_fr + t_br)) * 30.0
        self.heading = (self.heading + yaw_rate * dt) % 360.0

        self.pitch += ((t_fl + t_fr) - (t_bl + t_br)) * 10.0 * dt
        self.pitch = max(-45.0, min(45.0, self.pitch))

    def get_imu_telemetry(self) -> dict:
        return {
            "mode": self.mode,
            "depth": round(self.depth, 2),
            "target_depth": round(self.target_depth, 2),
            "heading": round(self.heading, 1),
            "pitch": round(self.pitch, 1),
            "ax": round(math.sin(math.radians(self.pitch)), 2),
            "ay": round(math.sin(math.radians(self.heading)), 2),
            "az": 9.81,
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

        try:
            data, _ = sock.recvfrom(256)
            packet = json.loads(data.decode('utf-8'))
            sub.last_packet_time = now
            if "mode" in packet:
                sub.mode = packet["mode"]
            if "target_depth" in packet:
                sub.target_depth = packet["target_depth"]
            if all(k in packet for k in ("fl", "fr", "bl", "br")):
                sub.pwms = packet
        except (BlockingIOError, json.JSONDecodeError, OSError):
            pass

        sub.update_physics(dt)
        time.sleep(0.05)

if __name__ == "__main__":
    run_simulation()
