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
    constexpr uint8_t SDA         = 21;
    constexpr uint8_t SCL         = 22;
}

// --- CONFIGURATION CONSTANTS ---
namespace Config {
    constexpr uint16_t PWM_NEUTRAL = 1500;  // Standard ESC Stop (us)
    constexpr uint16_t PWM_MIN     = 1100;  // Full Reverse (us)
    constexpr uint16_t PWM_MAX     = 1900;  // Full Forward (us)
    
    constexpr uint32_t WATCHDOG_TIMEOUT_MS  = 500;  // Stop horizontal thrust
    constexpr uint32_t EMERGENCY_TIMEOUT_MS = 2000; // Trigger auto-surface
    constexpr uint32_t TELEMETRY_INTERVAL_MS = 100;  // 10Hz Broadcast

    // PID Gain Constants for Depth Hold
    constexpr float KP = 60.0f;
    constexpr float KI = 1.2f;
    constexpr float KD = 15.0f;
}

// --- SYSTEM STATES ---
enum SystemMode {
    MODE_MANUAL = 0,
    MODE_DEPTH_HOLD = 1,
    MODE_EMERGENCY_SURFACE = 2
};

struct SubState {
    Adafruit_MPU6050 mpu;
    Servo thrusterFL, thrusterFR, thrusterBL, thrusterBR;
    
    SystemMode mode = MODE_MANUAL;
    uint32_t lastCommandTime = 0;
    bool imuHealthy = false;

    // Depth & PID State Variables
    float currentDepth = 0.0f;
    float targetDepth  = 0.0f;
    float pidIntegral  = 0.0f;
    float lastError    = 0.0f;
    uint32_t lastPIDTime = 0;
} sub;

// --- FUNCTION PROTOTYPES ---
void initializeHardware();
void applyThrust(int16_t fl, int16_t fr, int16_t bl, int16_t br);
void stopMotors();
void checkFailsafes();
void runDepthPID();
void processSerialPacket();
void readTelemetry();

void setup() {
    Serial.begin(115200);
    initializeHardware();
}

void loop() {
    processSerialPacket();
    checkFailsafes();

    if (sub.mode == MODE_DEPTH_HOLD) {
        runDepthPID();
    }

    readTelemetry();
}

void initializeHardware() {
    Wire.begin(Pins::SDA, Pins::SCL);
    
    if (sub.mpu.begin()) {
        sub.imuHealthy = true;
        sub.mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
        sub.mpu.setGyroRange(MPU6050_RANGE_250_DEG);
    }

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

void applyThrust(int16_t fl, int16_t fr, int16_t bl, int16_t br) {
    sub.thrusterFL.writeMicroseconds(constrain(fl, Config::PWM_MIN, Config::PWM_MAX));
    sub.thrusterFR.writeMicroseconds(constrain(fr, Config::PWM_MIN, Config::PWM_MAX));
    sub.thrusterBL.writeMicroseconds(constrain(bl, Config::PWM_MIN, Config::PWM_MAX));
    sub.thrusterBR.writeMicroseconds(constrain(br, Config::PWM_MIN, Config::PWM_MAX));
}

void stopMotors() {
    applyThrust(Config::PWM_NEUTRAL, Config::PWM_NEUTRAL, Config::PWM_NEUTRAL, Config::PWM_NEUTRAL);
}

void checkFailsafes() {
    uint32_t elapsed = millis() - sub.lastCommandTime;

    // Trigger auto-surface if connection is lost for over 2 seconds
    if (elapsed > Config::EMERGENCY_TIMEOUT_MS) {
        sub.mode = MODE_EMERGENCY_SURFACE;
        // Apply maximum negative throttle to vertical thrusters (ascent)
        applyThrust(1200, 1200, 1200, 1200); 
    } 
    else if (elapsed > Config::WATCHDOG_TIMEOUT_MS && sub.mode == MODE_MANUAL) {
        stopMotors();
    }
}

void runDepthPID() {
    uint32_t now = millis();
    float dt = (now - sub.lastPIDTime) / 1000.0f;
    if (dt <= 0.01f) return;
    sub.lastPIDTime = now;

    float error = sub.targetDepth - sub.currentDepth;
    sub.pidIntegral = constrain(sub.pidIntegral + (error * dt), -100.0f, 100.0f);
    float derivative = (error - sub.lastError) / dt;
    sub.lastError = error;

    float output = (Config::KP * error) + (Config::KI * sub.pidIntegral) + (Config::KD * derivative);
    int16_t correction = (int16_t)constrain(output, -300.0f, 300.0f);

    // Apply baseline neutral PWM plus PID vertical offset
    applyThrust(Config::PWM_NEUTRAL + correction,
                Config::PWM_NEUTRAL + correction,
                Config::PWM_NEUTRAL + correction,
                Config::PWM_NEUTRAL + correction);
}

void processSerialPacket() {
    if (!Serial.available()) return;

    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, Serial);
    if (error) return;

    sub.lastCommandTime = millis();

    if (doc.containsKey("mode")) {
        sub.mode = static_cast<SystemMode>(doc["mode"].as<int>());
    }

    if (doc.containsKey("target_depth")) {
        sub.targetDepth = doc["target_depth"].as<float>();
    }

    if (doc.containsKey("current_depth")) {
        sub.currentDepth = doc["current_depth"].as<float>();
    }

    if (sub.mode == MODE_MANUAL && doc.containsKey("fl")) {
        applyThrust(doc["fl"], doc["fr"], doc["bl"], doc["br"]);
    }
}

void readTelemetry() {
    static uint32_t lastRun = 0;
    if (millis() - lastRun < Config::TELEMETRY_INTERVAL_MS) return;
    lastRun = millis();

    StaticJsonDocument<128> doc;
    doc["mode"] = static_cast<int>(sub.mode);
    doc["depth"] = sub.currentDepth;
    doc["target_depth"] = sub.targetDepth;

    if (sub.imuHealthy) {
        sensors_event_t a, g, temp;
        sub.mpu.getEvent(&a, &g, &temp);
        doc["ax"] = round(a.acceleration.x * 100) / 100.0;
        doc["ay"] = round(a.acceleration.y * 100) / 100.0;
    }

    serializeJson(doc, Serial);
    Serial.println();
}
