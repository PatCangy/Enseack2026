// dj_leds.ino
// ─────────────────────────────────────────────────────────────────────────────
// WS2812B 5×10 LED matrix — controlled by the Python DJ pipeline via serial.
//
// Serial messages (115200 baud, newline-terminated):
//
//   MOOD,R,G,B,SIDE\n      — update wave color; next beat uses this color
//   BEAT,R,G,B,SIDE\n      — update color AND fire a wave immediately
//
// Idle behavior:
//   If no message arrives for IDLE_TIMEOUT_MS, reverts to CALM blue (0,0,255)
//   with a slow autonomous wave at CALM_BPM.
// ─────────────────────────────────────────────────────────────────────────────

#include <FastLED.h>

// ── Hardware ──────────────────────────────────────────────────────────────────
#define NUM_LEDS   50
#define DATA_PIN   31
#define LED_COLS   10
#define LED_ROWS    5

// ── Timing ────────────────────────────────────────────────────────────────────
#define CALM_BPM       60          // autonomous wave BPM when idle
#define FPS           240
#define IDLE_TIMEOUT_MS 2000UL     // ms before falling back to idle/CALM color

// ── Wave physics ──────────────────────────────────────────────────────────────
const float WAVE_SPEED = 6.0f;
const float WAVE_WIDTH = 1.2f;
const float DECAY      = 0.4f;

// ── Centre of the grid ────────────────────────────────────────────────────────
const float CX = 4.5f;
const float CY = 2.0f;

// ── State ─────────────────────────────────────────────────────────────────────
CRGB  leds[NUM_LEDS];
float brightness[NUM_LEDS];

CRGB  moodColor    = CRGB(0, 0, 255);   // default CALM blue
float waveRadius   = 1.0f;
float MAX_R        = 0.0f;
bool  waveActive   = false;

unsigned long lastBeat    = 0;
unsigned long lastFrame   = 0;
unsigned long lastSerial  = 0;          // tracks last received message
bool          idleMode    = true;       // true = no recent serial message
int           currentBpm  = CALM_BPM;

// Serial input buffer
#define BUF_SIZE 64
char   serialBuf[BUF_SIZE];
uint8_t bufPos = 0;

// ── Helpers ───────────────────────────────────────────────────────────────────

int ledIndex(int row, int col) {
    // Serpentine wiring: even rows left→right, odd rows right→left
    if (row % 2 == 0) return row * LED_COLS + col;
    else              return row * LED_COLS + (LED_COLS - 1 - col);
}

void triggerWave() {
    waveRadius = 0.0f;
    waveActive = true;
}

// ── Parse a complete serial line ──────────────────────────────────────────────
// Expected formats:
//   MOOD,R,G,B,SIDE
//   BEAT,R,G,B,SIDE
void parseLine(char* line) {
    // Tokenise
    char* token = strtok(line, ",");
    if (!token) return;

    bool isBeat = (strcmp(token, "BEAT") == 0);
    bool isMood = (strcmp(token, "MOOD") == 0);
    if (!isBeat && !isMood) return;

    int r = 0, g = 0, b = 0;

    token = strtok(NULL, ","); if (token) r = atoi(token);
    token = strtok(NULL, ","); if (token) g = atoi(token);
    token = strtok(NULL, ","); if (token) b = atoi(token);
    // SIDE field is received but not used by this sketch (the matrix is one panel)

    // Clamp to valid range
    r = constrain(r, 0, 255);
    g = constrain(g, 0, 255);
    b = constrain(b, 0, 255);

    moodColor   = CRGB(r, g, b);
    idleMode    = false;
    lastSerial  = millis();

    if (isBeat) {
        triggerWave();
        Serial.println("ACK");  // only confirm beat triggers, not every MOOD message
    }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(200);
    memset(brightness, 0, sizeof(brightness));

    // Pre-compute max radius from centre to corner
    for (int r = 0; r < LED_ROWS; r++) {
        for (int c = 0; c < LED_COLS; c++) {
            float dist = sqrtf(((float)c - CX) * ((float)c - CX) +
                               ((float)r - CY) * ((float)r - CY));
            if (dist > MAX_R) MAX_R = dist;
        }
    }

    lastFrame  = millis();
    lastBeat   = millis();
    lastSerial = millis();   // treat startup as a "recent message" so we don't
                              // immediately fire idle mode before the PC connects
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
    unsigned long now = millis();

    // ── 1. Read serial ────────────────────────────────────────────────────────
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (bufPos > 0) {
                serialBuf[bufPos] = '\0';
                parseLine(serialBuf);
                bufPos = 0;
            }
        } else if (bufPos < BUF_SIZE - 1) {
            serialBuf[bufPos++] = c;
        }
    }

    // ── 2. Idle timeout → revert to CALM blue ─────────────────────────────────
    if (!idleMode && (now - lastSerial >= IDLE_TIMEOUT_MS)) {
        idleMode  = true;
        moodColor = CRGB(0, 0, 255);
    }

    // ── 3. Autonomous beat in idle mode ───────────────────────────────────────
    unsigned long beatIntervalMs = 60000UL / (unsigned long)CALM_BPM;
    if (idleMode && (now - lastBeat >= beatIntervalMs)) {
        lastBeat = now;
        triggerWave();
    }

    // ── 4. Advance wave ───────────────────────────────────────────────────────
    float dt = (now - lastFrame) / 1000.0f;
    lastFrame = now;

    if (waveActive) {
        waveRadius += WAVE_SPEED * dt;
        if (waveRadius > MAX_R + WAVE_WIDTH) waveActive = false;
    }

    // ── 5. Render LEDs ────────────────────────────────────────────────────────
    for (int r = 0; r < LED_ROWS; r++) {
        for (int c = 0; c < LED_COLS; c++) {
            int idx = ledIndex(r, c);

            float distSq = ((float)c - CX) * ((float)c - CX) +
                           ((float)r - CY) * ((float)r - CY);

            // Decay previous brightness
            float b = brightness[idx] * DECAY;

            // Inject wave contribution
            if (waveActive) {
                float rMin = waveRadius - WAVE_WIDTH;
                float rMax = waveRadius + WAVE_WIDTH;
                if (distSq >= rMin * rMin && distSq <= rMax * rMax) {
                    float dist      = sqrtf(distSq);
                    float d         = fabsf(dist - waveRadius);
                    float intensity = cosf((d / WAVE_WIDTH) * (PI / 2.0f));
                    if (intensity > b) b = intensity;
                }
            }

            brightness[idx] = b;

            // Map brightness × mood color → LED
            uint8_t lvl = (uint8_t)(b * 255);
            leds[idx] = CRGB(
                (moodColor.r * lvl) >> 8,
                (moodColor.g * lvl) >> 8,
                (moodColor.b * lvl) >> 8
            );
        }
    }

    FastLED.show();
    delay(1000 / FPS);
}
