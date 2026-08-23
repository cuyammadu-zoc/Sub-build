#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

// --- HARDWARE PIN DEFINITIONS ---
namespace Pins {
    constexpr uint8_t THRUSTER_FL = 12; // Front-Left
    constexpr uint8_t THRUSTER_FR = 13; // Front-Right
    constexpr uint8_t THRUSTER_BL = 14; // Back-Left
    constexpr uint8_t THRUSTER_BR = 27; // Back-Right
    constexpr uint8_t SDA = 21;
    constexpr uint8_t SCL = 22;
}

// --- CONFIGURATION CONSTANTS ---
namespace Config {
    constexpr uint16_t PWM_NEUTRAL = 1500;  // Standard ESC Stop Signal (us)
    constexpr uint16_t PWM_MIN     = 1100;  // Full Reverse (us)
    constexpr uint16_t PWM_MAX     = 1900;  // Full Forward (us)
    constexpr uint32_t WATCHDOG_TIMEOUT_MS = 500; // Stop motors if no command in 500ms
    constexpr uint32_t TELEMETRY_INTERVAL_MS = 100; // 10Hz Telemetry Rate
}

// --- GLOBAL STATE ---
struct SubState {
    Adafruit_MPU6050 mpu;
    Servo thrusterFL, thrusterFR, thrusterBL, thrusterBR;
    uint32_t lastCommandTime = 0;
    bool imuHealthy = false;
} sub;

// --- FUNCTION PROTOTYPES ---
void initializeHardware();
void applyThrust(int16_t fl, int16_t fr, int16_t bl, int16_t br);
void stopMotors();
void checkWatchdog();
void readTelemetry();
void processSerialPacket();

void setup() {
    Serial.begin(115200);
    initializeHardware();
}

void loop() {
    processSerialPacket();
    checkWatchdog();
    readTelemetry();
}

// --- HARDWARE INITIALIZATION ---
void initializeHardware() {
    Wire.begin(Pins::SDA, Pins::SCL);
    
    // Initialize IMU
    if (sub.mpu.begin()) {
        sub.imuHealthy = true;
        sub.mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
        sub.mpu.setGyroRange(MPU6050_RANGE_250_DEG);
        sub.mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
        Serial.println("{\"status\":\"INFO\",\"msg\":\"IMU Initialized\"}");
    } else {
        Serial.println("{\"status\":\"WARN\",\"msg\":\"MPU6050 Init Failed\"}");
    }

    // Attach ESC Servo PWM Channels
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    
    sub.thrusterFL.setPeriodHertz(50);
    sub.thrusterFR.setPeriodHertz(50);
    sub.thrusterBL.setPeriodHertz(50);
    sub.thrusterBR.setPeriodHertz(50);

    sub.thrusterFL.attach(Pins::THRUSTER_FL, Config::PWM_MIN, Config::PWM_MAX);
    sub.thrusterFR.attach(Pins::THRUSTER_FR, Config::PWM_MIN, Config::PWM_MAX);
    sub.thrusterBL.attach(Pins::THRUSTER_BL, Config::PWM_MIN, Config::PWM_MAX);
    sub.thrusterBR.attach(Pins::THRUSTER_BR, Config::PWM_MIN, Config::PWM_MAX);

    stopMotors();
}

// --- MOTOR CONTROL & FAILSAFE ---
void applyThrust(int16_t fl, int16_t fr, int16_t bl, int16_t br) {
    sub.thrusterFL.writeMicroseconds(constrain(fl, Config::PWM_MIN, Config::PWM_MAX));
    sub.thrusterFR.writeMicroseconds(constrain(fr, Config::PWM_MIN, Config::PWM_MAX));
    sub.thrusterBL.writeMicroseconds(constrain(bl, Config::PWM_MIN, Config::PWM_MAX));
    sub.thrusterBR.writeMicroseconds(constrain(br, Config::PWM_MIN, Config::PWM_MAX));
    sub.lastCommandTime = millis();
}

void stopMotors() {
    sub.thrusterFL.writeMicroseconds(Config::PWM_NEUTRAL);
    sub.thrusterFR.writeMicroseconds(Config::PWM_NEUTRAL);
    sub.thrusterBL.writeMicroseconds(Config::PWM_NEUTRAL);
    sub.thrusterBR.writeMicroseconds(Config::PWM_NEUTRAL);
}

void checkWatchdog() {
    if (millis() - sub.lastCommandTime > Config::WATCHDOG_TIMEOUT_MS) {
        stopMotors();
    }
}

// --- PACKET PARSING (COMMAND INGESTION) ---
void processSerialPacket() {
    if (!Serial.available()) return;

    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, Serial);

    if (error) return; // Drop malformed packets

    if (doc.containsKey("fl") && doc.containsKey("fr") && doc.containsKey("bl") && doc.containsKey("br")) {
        int16_t fl = doc["fl"];
        int16_t fr = doc["fr"];
        int16_t bl = doc["bl"];
        int16_t br = doc["br"];
        applyThrust(fl, fr, bl, br);
    }
}

// --- TELEMETRY BROADCAST ---
void readTelemetry() {
    static uint32_t lastTelemetryRun = 0;
    if (millis() - lastTelemetryRun < Config::TELEMETRY_INTERVAL_MS) return;
    lastTelemetryRun = millis();

    if (!sub.imuHealthy) return;

    sensors_event_t a, g, temp;
    sub.mpu.getEvent(&a, &g, &temp);

    StaticJsonDocument<128> doc;
    doc["ax"] = round(a.acceleration.x * 100) / 100.0;
    doc["ay"] = round(a.acceleration.y * 100) / 100.0;
    doc["az"] = round(a.acceleration.z * 100) / 100.0;
    doc["temp"] = round(temp.temperature * 10) / 10.0;

    serializeJson(doc, Serial);
    Serial.println();
}
