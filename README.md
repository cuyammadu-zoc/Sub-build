# Custom Printed Submarine (Sub-Build) 🌊⚓

An open-source, full-stack underwater ROV system featuring embedded C++ ESP32 firmware, cloud compilation CI/CD pipelines, a Software-In-The-Loop (SITL) physics simulator, and a Pygame Ground Control Station with PS5 DualSense support.

---

## 🛠️ System Architecture

```text
 ┌──────────────────────────────────────┐          UDP Packets          ┌──────────────────────────────────────┐
 │    Ground Control Station (GCS)      │      (Port 8888 / JSON)       │        Submarine Controller          │
 │       `ground_control/gui.py`        │ ───────────────────────────►  │        (ESP32 / `src/main.cpp`)      │
 │                                      │                               │                 OR                   │
 │  * PS5 DualSense Gamepad Control    │ ◄───────────────────────────  │        SITL Physics Simulator        │
 │  * Real-time HUD Telemetry Stream    │        Telemetry Stream       │       (`sim/sub_simulator.py`)       │
 └──────────────────────────────────────┘                               └──────────────────────────────────────┘
