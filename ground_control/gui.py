import pygame
import socket
import json
import time

# --- NETWORK CONFIGURATION ---
TARGET_IP = "127.0.0.1"  # Connects to sim/sub_simulator.py or physical ESP32
TARGET_PORT = 8888

# --- COLOR PALETTE ---
BG_DARK      = (15, 23, 42)    # Slate dark
HUD_GREEN    = (34, 197, 94)   # Active neon green
HUD_CYAN     = (6, 182, 212)    # Telemetry cyan
HUD_ORANGE   = (249, 115, 22)  # Warning/Unlinked orange
MOTOR_GRAY   = (51, 65, 85)    # Gauge track
TEXT_WHITE   = (241, 245, 249)

class NetworkLink:
    """Handles non-blocking two-way UDP socket communications."""
    def __init__(self, target_ip, target_port):
        self.target_addr = (target_ip, target_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.last_telemetry_time = 0
        self.telemetry = {
            "depth": 0.0, "heading": 0.0, "pitch": 0.0, "temp": 20.0, "ax": 0.0, "ay": 0.0
        }

    def send_command(self, fl, fr, bl, br):
        packet = {"fl": fl, "fr": fr, "bl": bl, "br": br}
        try:
            self.sock.sendto(json.dumps(packet).encode("utf-8"), self.target_addr)
        except Exception:
            pass

    def update_telemetry(self):
        try:
            while True:
                data, _ = self.sock.recvfrom(512)
                self.telemetry.update(json.loads(data.decode("utf-8")))
                self.last_telemetry_time = time.time()
        except (BlockingIOError, json.JSONDecodeError, OSError):
            pass

    @property
    def is_connected(self):
        return (time.time() - self.last_telemetry_time) < 1.5


class HUD:
    """Renders graphical metrics, gauges, and artificial horizon."""
    def __init__(self, surface):
        self.surface = surface
        self.font = pygame.font.SysFont("Consolas", 13, bold=True)
        self.large_font = pygame.font.SysFont("Consolas", 18, bold=True)

    def draw_motor_bar(self, x, y, label, pwm_value):
        height, width = 120, 28
        pygame.draw.rect(self.surface, MOTOR_GRAY, (x, y, width, height), border_radius=4)
        
        normalized = (pwm_value - 1500) / 400.0  # -1.0 to +1.0
        fill_h = int((abs(normalized) * (height / 2)))
        fill_y = y + (height // 2) - fill_h if normalized >= 0 else y + (height // 2)
        color = HUD_GREEN if normalized != 0 else HUD_CYAN
        
        pygame.draw.rect(self.surface, color, (x + 2, fill_y, width - 4, fill_h), border_radius=2)
        pygame.draw.line(self.surface, TEXT_WHITE, (x, y + height // 2), (x + width, y + height // 2), 1)
        
        self.surface.blit(self.font.render(label, True, TEXT_WHITE), (x + 6, y - 18))
        self.surface.blit(self.font.render(f"{pwm_value}", True, HUD_CYAN), (x - 2, y + height + 4))

    def draw_attitude_indicator(self, cx, cy, radius, pitch, heading):
        pygame.draw.circle(self.surface, MOTOR_GRAY, (cx, cy), radius)
        
        pitch_clamped = max(-45, min(45, pitch))
        pitch_offset = int((pitch_clamped / 45.0) * (radius * 0.7))
        
        pygame.draw.line(self.surface, HUD_CYAN, (cx - radius + 8, cy + pitch_offset), (cx + radius - 8, cy + pitch_offset), 2)
        
        pygame.draw.circle(self.surface, HUD_GREEN, (cx, cy), 3)
        pygame.draw.line(self.surface, HUD_GREEN, (cx - 15, cy), (cx - 5, cy), 2)
        pygame.draw.line(self.surface, HUD_GREEN, (cx + 5, cy), (cx + 15, cy), 2)
        
        pygame.draw.circle(self.surface, HUD_CYAN, (cx, cy), radius, 2)
        self.surface.blit(self.font.render("ATTITUDE / HORIZON", True, TEXT_WHITE), (cx - 55, cy + radius + 10))

    def draw_header(self, connected):
        title = self.large_font.render("SUBMARINE GROUND CONTROL SYSTEM", True, HUD_GREEN)
        self.surface.blit(title, (20, 15))
        
        status_text = "LINK ONLINE" if connected else "SIMULATOR LINK"
        status_color = HUD_GREEN if connected else HUD_ORANGE
        status_bg = pygame.Rect(560, 15, 210, 26)
        
        pygame.draw.rect(self.surface, MOTOR_GRAY, status_bg, border_radius=4)
        pygame.draw.rect(self.surface, status_color, status_bg, width=2, border_radius=4)
        self.surface.blit(self.font.render(status_text, True, status_color), (status_bg.x + 12, status_bg.y + 5))


def apply_deadzone(value: float, threshold: float = 0.08) -> float:
    """Filters micro-stick drift on PS5 analog sticks."""
    return value if abs(value) > threshold else 0.0


def main():
    pygame.init()
    pygame.font.init()
    pygame.joystick.init()
    
    screen = pygame.display.set_mode((800, 480))
    pygame.display.set_caption("Submarine Ground Control HUD v2.0")
    clock = pygame.time.Clock()
    
    # Auto-initialize PS5 / USB Controller
    joystick = None
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()

    net = NetworkLink(TARGET_IP, TARGET_PORT)
    hud = HUD(screen)
    
    running = True
    while running:
        screen.fill(BG_DARK)
        net.update_telemetry()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        fl = fr = bl = br = 1500

        if joystick:
            # PS5 DualSense Axis Mapping
            axis_y = apply_deadzone(joystick.get_axis(1))  # Left Stick Up/Down
            axis_x = apply_deadzone(joystick.get_axis(0))  # Left Stick Left/Right

            throttle = int(-axis_y * 300)  # Push forward = increase throttle
            yaw = int(axis_x * 200)       # Push right = turn right

            fl += throttle + yaw; bl += throttle + yaw
            fr += throttle - yaw; br += throttle - yaw
        else:
            # Fallback Keyboard Controls
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w]: fl += 250; fr += 250; bl += 250; br += 250
            if keys[pygame.K_s]: fl -= 250; fr -= 250; bl -= 250; br -= 250
            if keys[pygame.K_a]: fl -= 150; bl -= 150; fr += 150; br += 150
            if keys[pygame.K_d]: fl += 150; bl += 150; fr -= 150; br -= 150

        # Safety Clamping (1100µs to 1900µs)
        fl, fr = max(1100, min(1900, fl)), max(1100, min(1900, fr))
        bl, br = max(1100, min(1900, bl)), max(1100, min(1900, br))

        net.send_command(fl, fr, bl, br)

        # Render Interface
        t = net.telemetry
        hud.draw_header(net.is_connected)
        
        hud.draw_motor_bar(40,  80, "FL", fl)
        hud.draw_motor_bar(95,  80, "FR", fr)
        hud.draw_motor_bar(150, 80, "BL", bl)
        hud.draw_motor_bar(205, 80, "BR", br)

        hud.draw_attitude_indicator(340, 160, 55, t.get("pitch", 0.0), t.get("heading", 0.0))

        # Telemetry Panel
        pygame.draw.rect(screen, MOTOR_GRAY, (450, 65, 320, 380), width=2, border_radius=6)
        
        controller_name = joystick.get_name()[:18] if joystick else "NOT CONNECTED"
        telem_lines = [
            "[ LIVE TELEMETRY DATA ]",
            f" DEPTH:   {t.get('depth', 0.0):.2f} m",
            f" HEADING: {t.get('heading', 0.0):.1f}°",
            f" PITCH:   {t.get('pitch', 0.0):.1f}°",
            f" TEMP:    {t.get('temp', 0.0):.1f} °C",
            "",
            "[ INPUT DEVICE ]",
            f" HARDWARE: {controller_name}",
            f" CONTROL:  {'PS5 DUALSENSE' if joystick else 'KEYBOARD WASD'}"
        ]
        
        for idx, line in enumerate(telem_lines):
            color = HUD_CYAN if "[" in line else (HUD_GREEN if joystick and "HARDWARE" in line else TEXT_WHITE)
            screen.blit(hud.font.render(line, True, color), (465, 85 + (idx * 22)))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()
