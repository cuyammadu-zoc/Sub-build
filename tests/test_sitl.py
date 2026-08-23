import sys
import os
import time

# Add repository root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sim.sub_simulator import VirtualSubmarine

def test_basic_telemetry():
    sub = VirtualSubmarine()
    sub.pwms = {"fl": 1700, "fr": 1700, "bl": 1700, "br": 1700}
    for _ in range(20):
        sub.update_physics(0.05)
        
    telem = sub.get_imu_telemetry()
    assert "depth" in telem, "Missing depth key"
    assert "heading" in telem, "Missing heading key"
    assert telem["az"] == 9.81, "Invalid gravity vector"
    print("[PASS] Basic Telemetry & Physics Test Passed!")

def test_depth_hold_pid():
    sub = VirtualSubmarine()
    sub.mode = 1  # DEPTH_HOLD Mode
    sub.depth = 0.0
    sub.target_depth = 2.0
    
    # Step physics forward 2 seconds (40 steps at 0.05s dt)
    for _ in range(40):
        sub.update_physics(0.05)
        
    telem = sub.get_imu_telemetry()
    assert telem["depth"] > 0.5, "Submarine failed to dive toward target depth"
    assert telem["mode"] == 1, "Incorrect mode state"
    print("[PASS] Closed-Loop PID Depth Hold Test Passed!")

def test_emergency_auto_surface():
    sub = VirtualSubmarine()
    sub.depth = 3.0
    sub.last_packet_time = time.time() - 3.0  # Simulate 3-second signal timeout
    
    # Trigger physics step to check timeout
    sub.update_physics(0.1)
    
    telem = sub.get_imu_telemetry()
    assert telem["mode"] == 2, "Failsafe failed to switch to EMERGENCY_SURFACE mode"
    
    # Step physics forward during ascent
    for _ in range(50):
        sub.update_physics(0.1)
        
    assert sub.get_imu_telemetry()["depth"] < 3.0, "Submarine failed to ascend during emergency surface"
    print("[PASS] Emergency Auto-Surface Failsafe Test Passed!")

if __name__ == "__main__":
    test_basic_telemetry()
    test_depth_hold_pid()
    test_emergency_auto_surface()
