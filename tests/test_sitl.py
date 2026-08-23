import sys
import os

# Add repository root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sim.sub_simulator import VirtualSubmarine

def test_sub_physics_integration():
    sub = VirtualSubmarine()
    
    # Simulate full forward thrust (1700us)
    sub.pwms = {"fl": 1700, "fr": 1700, "bl": 1700, "br": 1700}
    
    # Step physics forward for 1 second (20 steps at 0.05s dt)
    for _ in range(20):
        sub.update_physics(0.05)
        
    telem = sub.get_imu_telemetry()
    
    # Verify telemetry structure and values
    assert "depth" in telem, "Telemetry missing depth key"
    assert "heading" in telem, "Telemetry missing heading key"
    assert telem["az"] == 9.81, "Gravity vector invalid"
    print("[PASS] Cloud SITL Physics Integration Test Passed!")

if __name__ == "__main__":
    test_sub_physics_integration()
