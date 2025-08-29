#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <Adafruit_Fingerprint.h>
#include <SoftwareSerial.h>
#include <U8g2lib.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

const char* ssid = "realme C51";
const char* password = "123456789";
char flask_host[32] = "";  //this will be set dynamicaaly via http post from flask
const int flask_port = 5000;

U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0);
SoftwareSerial fingerSerial(D5, D6);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&fingerSerial);
AsyncWebServer server(80);

IPAddress local_IP(10, 178, 180, 30);     // Use 30 or any free IP
IPAddress gateway(10, 178, 180, 57);      // Your phone's hotspot IP
IPAddress subnet(255, 255, 255, 0);

bool attendanceMode = false;
bool enrollRequested = false;
int enrollID = -1;
bool enrolling = false;
int lastMatchedID = -1;  // globally track the last detected fingerprint
bool newMatchAvailable = false;
unsigned long lastCheck =0;
bool flaskIpSet = false; 

void displayStatus(const String& message) {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x10_tf);
  // u8g2.drawStr(0, 12, "WiFi Connected");
  // u8g2.drawStr(0, 24, "Server Ready");
  u8g2.drawStr(0, 24, message.c_str());
  u8g2.sendBuffer();
}

void showStartupMessage() {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(0, 12, "Welcome");
  u8g2.drawStr(0, 24, "Smart Attendance");
  u8g2.drawStr(0, 36, "WiFi Connected");
  u8g2.sendBuffer();
}

void showSerialMenu() {
  Serial.println("\n------ Fingerprint Menu ------");
  Serial.println("1. Enroll Fingerprint");
  Serial.println("2. Delete Fingerprint");
  Serial.println("3. Detect Fingerprint");
  Serial.println("4. View Enrolled IDs");
  Serial.println("5. Start Attendance");
  Serial.println("6. Stop Attendance");
  Serial.print("Select option (1–6): ");
}


bool postToFlask(const String& endpoint, const String& json) {
  if (strlen(flask_host) == 0) {
    Serial.println("❌ Flask IP not set. Cannot send POST.");
    return false;
  }

  WiFiClient client;
  HTTPClient http;
  String url = "http://" + String(flask_host) + ":" + String(flask_port) + endpoint;

  Serial.println(">> Posting to Flask at: " + url);
  Serial.println(">> Payload: " + json);

  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(json);

  Serial.print("<< Response Code: ");
  Serial.println(code);

  if (code > 0) {
    String payload = http.getString();
    Serial.println("<< Response Body: " + payload);
  } else {
    Serial.println("<< POST failed: " + http.errorToString(code));
  }

  http.end();
  return (code == 200);
}

void handleSetFlaskIP(AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
  StaticJsonDocument<200> doc;
  DeserializationError err = deserializeJson(doc, data);
  if (err) {
    request->send(400, "application/json", "{\"error\": \"Invalid JSON\"}");
    return;
  }

  String receivedIP = doc["ip"];
  if (receivedIP.length() > 0) {
    receivedIP.trim();
    strcpy(flask_host, receivedIP.c_str());

    //  Immediately send response to avoid timeout/panic
    AsyncWebServerResponse *res = request->beginResponse(200, "application/json", "{\"status\": \"flask ip set\"}");
    res->addHeader("Access-Control-Allow-Origin", "*");
    request->send(res);

    //  Only after response, do logging / OLED / delay
    delay(5);  // give time for client to close socket
    Serial.println("✅ Flask IP received: " + receivedIP);
    displayStatus("Flask IP received!");
    delay(1000);
    showStartupMessage();

  } else {
    request->send(400, "application/json", "{\"error\": \"Empty IP\"}");
  }
}






void setup() {
  Serial.begin(115200);
  u8g2.begin();
  finger.begin(57600);

  // WiFi.config(local_IP, gateway, subnet); 
  WiFi.begin(ssid, password);
  displayStatus("Connecting WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("ESP Ip address:");
  Serial.println(WiFi.localIP()); //this will change every time

u8g2.clearBuffer();
u8g2.setFont(u8g2_font_6x10_tf);
u8g2.drawStr(0, 12, "WiFi Connected");
u8g2.drawStr(0, 24, "ESP IP:");
u8g2.drawStr(0, 36, WiFi.localIP().toString().c_str());
u8g2.sendBuffer();
delay(3000); // hold display for 3 seconds

  // displayStatus("WiFi Connected");
  showStartupMessage();



  // ========== Routes ==========
  //  server.on("/ip", HTTP_GET, [](AsyncWebServerRequest *request){
  // request->send(200, "text/plain", WiFi.localIP().toString());
  //  });

 // Correct handler for /receive_flask_ip POST
  server.on("/receive_flask_ip", HTTP_POST, [](AsyncWebServerRequest *request){}, NULL, handleSetFlaskIP);

  server.on("/ping", HTTP_GET, [](AsyncWebServerRequest *request) {
  request->send(200, "text/plain", "pong");
  });

  server.on("/verify_ip", HTTP_GET, [](AsyncWebServerRequest *request) {
  String response = "{\"ip\":\"" + String(flask_host) + "\"}";
  request->send(200, "application/json", response);
  });



  server.on("/test_json", HTTP_GET, [](AsyncWebServerRequest *request) {
    AsyncWebServerResponse *res = request->beginResponse(200, "application/json", "{\"status\":\"ok\"}");
    res->addHeader("Access-Control-Allow-Origin", "*");
    request->send(res);
  });

  server.on("/list", HTTP_GET, [](AsyncWebServerRequest *request) {
  finger.getTemplateCount(); // Needed to refresh template info
  String ids = "[";
  for (int i = 1; i < 128; i++) {
    if (finger.loadModel(i) == FINGERPRINT_OK) {
      ids += String(i) + ",";
    }
  }
  if (ids.endsWith(",")) ids.remove(ids.length() - 1);
  ids += "]";
  AsyncWebServerResponse *res = request->beginResponse(200, "application/json", "{\"used_ids\": " + ids + "}");
  res->addHeader("Access-Control-Allow-Origin", "*");
  request->send(res);
});


  server.on("/start_scan", HTTP_GET, [](AsyncWebServerRequest *request) {
  if (strlen(flask_host) == 0) {
    displayStatus("Waiting for Flask IP...");
    delay(2000);
    showStartupMessage();
  } else {
    attendanceMode = true;
    displayStatus("Scan Started");
  }

  AsyncWebServerResponse *res = request->beginResponse(200, "application/json", "{\"status\":\"ok\"}");
  res->addHeader("Access-Control-Allow-Origin", "*");
  request->send(res);
  });


  server.on("/stop_scan", HTTP_GET, [](AsyncWebServerRequest *request) {
    attendanceMode = false;
    displayStatus("Scan Stopped");
    delay(2000);  // Optional: show message for 2 seconds
    showStartupMessage();

    AsyncWebServerResponse *res = request->beginResponse(200, "application/json", "{\"status\":\"stopped\"}");
    res->addHeader("Access-Control-Allow-Origin", "*");
    request->send(res);
  });

  server.on("/get_match", HTTP_GET, [](AsyncWebServerRequest *request) {
  StaticJsonDocument<128> doc;
  if (newMatchAvailable) {
    doc["match"] = true;
    doc["fingerprint_id"] = lastMatchedID;
    newMatchAvailable = false;  // consume match
  } else {
    doc["match"] = false;
  }

  String response;
  serializeJson(doc, response);
  AsyncWebServerResponse *res = request->beginResponse(200, "application/json", response);
  res->addHeader("Access-Control-Allow-Origin", "*");
  request->send(res);
  });


  server.onNotFound([](AsyncWebServerRequest *request) {
    String path = request->url();

    // Handle /enroll/<id>
    if (path.startsWith("/enroll/")) {
  int id = path.substring(8).toInt();
  if (id > 0 && id < 128 && finger.loadModel(id) != FINGERPRINT_OK) {
    if (strlen(flask_host) == 0) {
    displayStatus("Waiting for Flask IP...");
    delay(2000);
    showStartupMessage();
    }

    enrollID = id;
    enrolling = true;
    AsyncWebServerResponse* res = request->beginResponse(200, "application/json", "{\"status\":\"pending\"}");
    res->addHeader("Access-Control-Allow-Origin", "*");
    request->send(res);
  } else {
    request->send(400, "application/json", "{\"status\":\"fail\",\"message\":\"Invalid or used ID\"}");
  }
}

    // Handle /delete/<id>
    if (path.startsWith("/delete/")) {
      int id = path.substring(8).toInt();
      StaticJsonDocument<128> doc;
      doc["id"] = id;
      if (finger.deleteModel(id) == FINGERPRINT_OK) {
        doc["status"] = "Deleted";
      } else {
        doc["status"] = "Failed to delete";
      }
      String json;
      serializeJson(doc, json);
      AsyncWebServerResponse *res = request->beginResponse(200, "application/json", json);
      res->addHeader("Access-Control-Allow-Origin", "*");
      request->send(res);
      return;
    }

    // 404 fallback
    request->send(404, "application/json", "{\"error\":\"Route not found\"}");
  });


  
  server.begin();
  // displayMenuOLED();
  showSerialMenu();
  Serial.println("Server started\n");
  displayStatus("Server Ready");
  delay(1000);
  showStartupMessage();


}

void loop() {
 

  // Serial Menu
  if (Serial.available()) {
    int option = Serial.parseInt();
    switch (option) {
      case 1:
         Serial.print("Enter ID to Enroll (1-127): ");
         while (!Serial.available());
         enrollID = Serial.parseInt();
       
         if (enrollID > 0 && enrollID < 128 && finger.loadModel(enrollID) != FINGERPRINT_OK) {
           Serial.println("Starting Enrollment...");
           displayStatus("Place Finger...");
       
           bool success = doEnrollment(enrollID);
           displayStatus(success ? "Enroll Success" : "Enroll Failed");
           Serial.println(success ? "Enrollment successful" : "Enrollment failed");
       
           // Notify Flask
           String jsonPayload = "{\"fingerprint_id\":" + String(enrollID) +
                                ", \"status\":\"" + (success ? "success" : "fail") + "\"}";
           postToFlask("/enroll_result", jsonPayload);
       
           enrollID = -1;
         } else {
           Serial.println("Invalid or used ID.");
           displayStatus("Invalid or Used ID");
           delay(2000);
           showStartupMessage();
         }
         delay(2000);
         showStartupMessage();
         break;
  
    
      case 2:
        Serial.print("Enter ID to Delete: ");
        while (!Serial.available());
        {
          int delID = Serial.parseInt();
          if (finger.deleteModel(delID) == FINGERPRINT_OK) {
            Serial.println("Deleted successfully.");
            displayStatus("Deleted ID " + String(delID));
          } else {
            Serial.println("Delete failed.");
            displayStatus("Delete Failed");
          }
        }
        delay(2000);
        showStartupMessage();
        break;

      case 3:
        Serial.println("Place finger to Detect...");
        displayStatus("Detecting...");
        if (finger.getImage() == FINGERPRINT_OK &&
            finger.image2Tz() == FINGERPRINT_OK &&
            finger.fingerFastSearch() == FINGERPRINT_OK) {
          int id = finger.fingerID;
          Serial.println("Matched ID: " + String(id));
          displayStatus("Matched ID: " + String(id));
        } else {
          Serial.println("No match found.");
          displayStatus("No match");
        }
        delay(2000);
        showStartupMessage();
        break;

      case 4:
        Serial.println("Enrolled IDs:");
        for (int i = 1; i < 128; i++) {
          if (finger.loadModel(i) == FINGERPRINT_OK) {
            Serial.println("ID " + String(i) + " is enrolled");
          }
        }
        break;

      case 5:
        attendanceMode = true;
        Serial.println("Scan Started");
        displayStatus("Scan Started");
        break;

      case 6:
        attendanceMode = false;
        Serial.println("Scan Stopped");
        displayStatus("Scan Stopped");
        break;
    }
    showSerialMenu();
  }
  
  // Background Enrollment (Triggered by Flask)
  if (enrolling && enrollID > 0) {
  Serial.println(">> Enrollment triggered via Flask");

  bool success = doEnrollment(enrollID);

  //  Send result to Flask immediately
  String jsonPayload = "{\"fingerprint_id\":" + String(enrollID) +
                       ", \"status\":\"" + (success ? "success" : "fail") + "\"}";
  postToFlask("/enroll_result", jsonPayload);  // <-- First priority!

  //  Then show result on OLED
  displayStatus(success ? "Enroll Success" : "Enroll Failed");
  delay(2000);  // Optional: just for user to see result

  enrolling = false;
  enrollID = -1;
  showStartupMessage();
  }




  // Attendance mode (background)
  if (attendanceMode) {
  if (finger.getImage() == FINGERPRINT_OK &&
  finger.image2Tz() == FINGERPRINT_OK &&
  finger.fingerFastSearch() == FINGERPRINT_OK) {

  lastMatchedID = finger.fingerID;
  newMatchAvailable = true;

  Serial.println("Student matched: ID " + String(lastMatchedID));
  displayStatus("Student ID: " + String(lastMatchedID));

  String payload = "{\"fingerprint_id\":" + String(lastMatchedID) + "}";
  postToFlask("/record_attendance", payload);

  delay(1000);
  displayStatus("Ready for next...");
}
  }
}

bool doEnrollment(int id) {
  displayStatus("Place finger...");
  unsigned long start = millis();
  while ((millis() - start) < 10000) {
    if (finger.getImage() == FINGERPRINT_OK) break;
    yield();
  }
  if (finger.image2Tz(1) != FINGERPRINT_OK) return false;

  displayStatus("Remove finger...");
  while (finger.getImage() != FINGERPRINT_NOFINGER) {
    delay(50); yield();
  }

  displayStatus("Place again...");
  start = millis();
  while ((millis() - start) < 10000) {
    if (finger.getImage() == FINGERPRINT_OK) break;
    yield();
  }
  if (finger.image2Tz(2) != FINGERPRINT_OK) return false;
  if (finger.createModel() != FINGERPRINT_OK) return false;
  if (finger.storeModel(id) != FINGERPRINT_OK) return false;

  return true;
}
