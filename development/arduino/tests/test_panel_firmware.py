"""Host C++ behavior checks with simulated Arduino/Wire/NeoPixel APIs."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FirmwareTests(unittest.TestCase):
    def test_scanner_inputs_watchdog_and_disarm(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "Wire.h").write_text('''#pragma once
#include <stdint.h>
struct WireMock {
 bool connected=true; int key=-1; uint8_t mask=0;
 void begin() {} void setClock(int) {} void beginTransmission(int) {}
 void write(uint8_t m) {mask=m;} int endTransmission() {return connected?0:1;}
 int requestFrom(uint8_t,uint8_t) {return connected?1:0;}
 int read() {if(key<0)return 255;uint8_t n[]={14,13,11,7};return mask==0xF0?(n[key%4]<<4)|15:240|n[key/4];}
}; inline WireMock Wire;
''')
            (work / "Adafruit_NeoPixel.h").write_text('''#pragma once
#include <stdint.h>
#define NEO_GRB 0
#define NEO_KHZ800 0
struct Adafruit_NeoPixel {
 uint32_t value=0,pixels[42]={};int shows=0;Adafruit_NeoPixel(int n,int,int) {if(n!=42)__builtin_trap();}
 void begin(){}void setBrightness(int){}void clear(){value=0;for(auto &p:pixels)p=0;}void show(){shows++;}
 uint32_t Color(uint8_t r,uint8_t g,uint8_t b){return (r<<16)|(g<<8)|b;}
 uint32_t getPixelColor(int i){return pixels[i];}void setPixelColor(int i,uint32_t v){pixels[i]=v;value=pixels[0];}
};
''')
            (work / "TM1637Display.h").write_text('''#pragma once
#include <stdint.h>
struct TM1637Display {
 int value=-1;uint8_t dots=0;bool leading=false;
 TM1637Display(int,int){} void setBrightness(int){} void clear(){value=-1;}
 void showNumberDecEx(int n,uint8_t d,bool z){value=n;dots=d;leading=z;}
};
''')
            (work / "SPI.h").write_text("#pragma once\nstruct SPIMock {void begin(){}}; inline SPIMock SPI;\n")
            (work / "MFRC522.h").write_text('''#pragma once
#include <stdint.h>
struct MFRC522 {
 enum {VersionReg=0,TxModeReg=1,RxModeReg=2,ModWidthReg=3,TxControlReg=4,RxGain_max=112,STATUS_OK=0,STATUS_COLLISION=2,STATUS_TIMEOUT=3};
 struct UID {} uid;uint8_t version=0,gain=0,antenna=0;int initializations=0;bool tag=false,readOK=true;
 void PCD_SetAntennaGain(uint8_t v){gain=v;}uint8_t PCD_GetAntennaGain(){return gain;}
 void PCD_WriteRegister(int,int){}
 uint8_t PICC_RequestA(uint8_t*,uint8_t*){return tag?STATUS_OK:STATUS_TIMEOUT;}
 uint8_t PICC_Select(UID*){return readOK?STATUS_OK:STATUS_TIMEOUT;}
 MFRC522(int,int){}void PCD_Init(){antenna=3;initializations++;}uint8_t PCD_ReadRegister(int reg){return reg==TxControlReg?antenna:version;}
 bool PICC_IsNewCardPresent(){return tag;}bool PICC_ReadCardSerial(){return readOK;}
 void PICC_HaltA(){tag=false;}void PCD_StopCrypto1(){}
};
''')
            (work / "checks.cpp").write_text('''#include <cstdint>
#include <cstring>
#include <string>
#include <sstream>
#include <cassert>
#include <iostream>
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define LED_BUILTIN 13
#define A0 54
#define A1 55
int lightValue=70, tankValue=267;
int analogRead(int p){assert(p==A0||p==A1);return p==A0?lightValue:tankValue;}
unsigned long clockNow=0;int pins[80]={};
unsigned long millis(){return clockNow;}
void pinMode(int,int){}void digitalWrite(int p,int v){pins[p]=v;}int digitalRead(int p){return pins[p];}
struct SerialMock {std::string output;void begin(int){}int available(){return 0;}char read(){return 0;}
 template<class T>void print(T v){std::ostringstream s;s<<v;output+=s.str();}
 void print(uint8_t v){print((int)v);}void println(){output+='\\n';}
 template<class T>void println(T v){print(v);println();}
} Serial;
''' + '#include "' + str(ROOT / "BenchController/BenchController.ino") + '"\n' + '''
int main(){
 setup();assert(entryReader.gain==112);assert(!armed&&!ledOn&&pins[5]==LOW&&pins[9]==LOW&&panelPixel.value==0);
 strcpy(command,"RFID");handleCommand();assert(!rfidReady&&Serial.output.find("RFID MISSING")!=std::string::npos);
 entryReader.version=0x92;strcpy(command,"RFID");handleCommand();assert(rfidReady&&Serial.output.find("RFID READY")!=std::string::npos);
 entryReader.tag=true;clockNow=100;updateRfid(false);assert(!entryReader.tag);
 entryReader.tag=true;clockNow=200;Serial.output.clear();updateRfid(true);assert(Serial.output=="RFID TAG\\n");
 clockNow=300;updateRfid(true);assert(Serial.output=="RFID TAG\\n");
 assert(rfidResponses==2&&rfidSelectFailures==0);
 entryReader.tag=true;entryReader.readOK=false;clockNow=400;updateRfid(true);
 assert(rfidSelectFailures==1&&rfidResponses==3);entryReader.tag=false;entryReader.readOK=true;
 strcpy(command,"RFID DIAG");handleCommand();assert(Serial.output.find("RFID DIAG 3 1 0 3 112")!=std::string::npos);
 // Quick reconnect between polls: version present, cached ready true, antenna off.
 entryReader.version=0x92;rfidReady=true;entryReader.antenna=0;
 int inits=entryReader.initializations;strcpy(command,"RFID");handleCommand();assert(rfidReady&&entryReader.antenna==3&&entryReader.initializations==inits+1);
 strcpy(command,"RFID");handleCommand();assert(entryReader.initializations==inits+1);
 strcpy(command,"RFID RESET");handleCommand();assert(rfidReady&&entryReader.initializations==inits+2);
 entryReader.version=0;strcpy(command,"RFID");handleCommand();assert(!rfidReady);
 entryReader.version=0x92;entryReader.antenna=0;strcpy(command,"RFID");handleCommand();assert(rfidReady&&entryReader.antenna==3);
 entryReader.version=0;strcpy(command,"RFID");handleCommand();assert(!rfidReady);
 clockNow=0;Serial.output.clear();
 strcpy(command,"LIGHT");handleCommand();assert(Serial.output.find("LIGHT A0 70")!=std::string::npos&&!armed&&pins[9]==LOW);
 Serial.output.clear();strcpy(command,"LEVEL");handleCommand();assert(Serial.output.find("LEVEL A1 267")!=std::string::npos&&!armed&&pins[9]==LOW);
 assert(setReceiverCalibration("50 80"));
 assert(receiverBroken(49,false)&&!receiverBroken(81,true));
 assert(receiverBroken(60,true)&&!receiverBroken(60,false));
 for(const char *bad : {"65556 65577","+20 41","20 41 extra","0 41","20 1023","41 20","20 41 "})assert(!setReceiverCalibration(bad));
 assert(setReceiverCalibration("20 41"));
 strcpy(command,"CAL 21 42");handleCommand();assert(receiverBreakThreshold==21&&receiverClearThreshold==42);
 strcpy(command,"CAL 20 41");handleCommand();assert(receiverBreakThreshold==20&&receiverClearThreshold==41);
 assert(!panelStable[0]);
 assert(receiverBroken(6,false));assert(!receiverBroken(70,true));
 assert(receiverBroken(20,true)&&!receiverBroken(20,false));
 assert(receiverBroken(41,true)&&!receiverBroken(41,false));
 assert(receiverBroken(30,true)&&!receiverBroken(30,false));
 assert(receiverBroken(19,false)&&!receiverBroken(42,true));
 assert(panelTimer.value==-1);assert(panelTime("150")&&panelTimer.value==230&&panelTimer.dots==0x40&&panelTimer.leading);
 assert(panelTime("59")&&panelTimer.value==59);assert(panelTime("60")&&panelTimer.value==100);
 assert(panelTime("0")&&panelTimer.value==0);assert(panelTime("5999")&&panelTimer.value==9959);
 assert(!panelTime("6000")&&!panelTime("-1")&&!panelTime("150x")&&!panelTime(""));
 for(int i=0;i<16;i++){Wire.key=i;assert(readPanelKey()=="123F456F789F*0#F"[i]);}
 Wire.key=-1;assert(readPanelKey()=='N');Wire.connected=false;assert(readPanelKey()=='F'&&!keypadReady);Wire.connected=true;
 assert(panelCommand("PANEL",false)&&!panelDiagnostic);
 strcpy(command,"ARM");handleCommand();assert(armed);
 strcpy(command,"PANEL");handleCommand();assert(panelDiagnostic);
 // Door outputs release on disarm, bad command and watchdog, independent of laser.
 strcpy(command,"DOORS 1 1");handleCommand();assert(pins[22]==HIGH&&pins[23]==HIGH);
 strcpy(command,"OFF");handleCommand();assert(pins[22]==LOW&&pins[23]==LOW);
 strcpy(command,"DOORS 1 0");handleCommand();assert(pins[22]==LOW&&pins[23]==LOW);
 strcpy(command,"ARM");handleCommand();strcpy(command,"DOORS 1 0");handleCommand();assert(pins[22]==HIGH&&pins[23]==LOW);
 strcpy(command,"DOORS 1 2");handleCommand();assert(!armed&&pins[22]==LOW&&pins[23]==LOW);
 strcpy(command,"ARM");handleCommand();strcpy(command,"DOORS 1 1");handleCommand();
 clockNow=1001;loop();assert(!armed&&pins[22]==LOW&&pins[23]==LOW);
 clockNow=0;strcpy(command,"ARM");handleCommand();strcpy(command,"PANEL");handleCommand();
 strcpy(command,"DOORTEST 1");handleCommand();assert(pins[22]==LOW&&pins[23]==HIGH);
 clockNow=5000;updatePanel(true);doorTestStarted=0;lastHeartbeat=5000;loop();assert(pins[22]==LOW&&pins[23]==LOW);
 clockNow=0;lastHeartbeat=0;
 // Analog transitions are hysteretic and retain the existing 30ms debounce.
 lightValue=6;clockNow=10;loop();assert(!panelStable[0]);
 clockNow=41;loop();assert(panelStable[0]);
 lightValue=30;clockNow=80;loop();assert(panelStable[0]);
 lightValue=70;clockNow=81;loop();assert(panelStable[0]);
 clockNow=112;loop();assert(!panelStable[0]);
 lightValue=30;clockNow=115;loop();assert(!panelStable[0]);
 lightValue=70;
 // Retired D2 button must not alter receiver state.
 pins[2]=HIGH;clockNow=116;loop();assert(!panelStable[0]);
 Serial.output.clear();pins[3]=HIGH;clockNow=120;loop();assert(!panelStable[1]);
 clockNow=151;loop();assert(!panelStable[1]&&Serial.output.find("INPUT 1 1")==std::string::npos);
 Serial.output.clear();clockNow=180;loop();assert(Serial.output.empty());
 strcpy(command,"ON");handleCommand();assert(ledOn&&pins[5]==HIGH&&pins[9]==HIGH);
 Serial.output.clear();strcpy(command,"OUTPUT");handleCommand();assert(Serial.output.find("OUTPUT 1 1 1")!=std::string::npos);
 pins[9]=LOW;Serial.output.clear();strcpy(command,"OUTPUT");handleCommand();assert(Serial.output.find("OUTPUT 1 1 0")!=std::string::npos);pins[9]=HIGH;
 strcpy(command,"PAUSE");handleCommand();assert(armed&&!ledOn&&pins[9]==LOW);
 strcpy(command,"ON");handleCommand();assert(pins[9]==HIGH);
 strcpy(command,"OFF");handleCommand();assert(!armed&&pins[9]==LOW);
 strcpy(command,"ON");handleCommand();assert(!armed&&pins[9]==LOW);
 strcpy(command,"ARM");handleCommand();strcpy(command,"ON");handleCommand();
 strcpy(command,"BAD");handleCommand();assert(!armed&&pins[9]==LOW);
 strcpy(command,"ARM");handleCommand();strcpy(command,"ON");handleCommand();
 strcpy(command,"HELLO");handleCommand();assert(!armed&&pins[9]==LOW);
 strcpy(command,"ARM");handleCommand();strcpy(command,"ON");handleCommand();
 clockNow=1181;loop();assert(!armed&&!ledOn&&pins[5]==LOW&&pins[9]==LOW&&panelPixel.value==0);
 assert(panelTimer.value==-1);
 assert(Serial.output.find("FAULT WATCHDOG")!=std::string::npos);
 strcpy(command,"HELLO");handleCommand();assert(!panelDiagnostic);
 pins[4]=HIGH;clockNow=1500;updatePanel(true);clockNow=1550;updatePanel(true);assert(!panelStable[2]);
 assert(STATUS_PIXEL_COUNT==42);
 clockNow=2000;panelColor(255,0,0);updateStatusAnimation();
 clockNow=2120;updateStatusAnimation();assert(panelPixel.getPixelColor(0)==0xFF0000);assert(panelPixel.getPixelColor(21)==0x200000);
 clockNow=2300;updateStatusAnimation();assert(panelPixel.getPixelColor(0)==0x200000);assert(panelPixel.getPixelColor(21)==0xFF0000);
 clockNow=2520;updateStatusAnimation();assert(panelPixel.getPixelColor(0)==0xFF0000);
 clockNow=2800;updateStatusAnimation();assert(panelPixel.getPixelColor(21)==0xFF0000);
 clockNow=3260;updateStatusAnimation();assert(!statusAnimating);
 for(int i=0;i<42;i++)assert(panelPixel.getPixelColor(i)==0xFF0000);
 clockNow=4000;panelColor(0,255,0);auto start=statusStarted;
 clockNow=4300;panelColor(0,255,0);assert(statusStarted==start);updateStatusAnimation();
 assert(panelPixel.getPixelColor(6*3)==0x00FF00);assert(panelPixel.getPixelColor(0)==0xFF0000);
 for(int row=0;row<14;row++){assert(panelPixel.getPixelColor(row*3)==panelPixel.getPixelColor((13-row)*3));for(int col=1;col<3;col++)assert(panelPixel.getPixelColor(row*3)==panelPixel.getPixelColor(row*3+col));}
 auto current=panelPixel.getPixelColor(3*3);panelColor(0,0,255);assert(panelPixel.getPixelColor(3*3)==current);
 clockNow=5000;updateStatusAnimation();for(int i=0;i<42;i++)assert(panelPixel.getPixelColor(i)==0x0000FF);
 int shows=panelPixel.shows;clockNow=6000;panelColor(0,0,255);updateStatusAnimation();assert(panelPixel.shows==shows);
 panelColor(255,180,0);clockNow=6200;updateStatusAnimation();panelOff();assert(!statusAnimating);
 for(int i=0;i<42;i++)assert(panelPixel.getPixelColor(i)==0);
 clockNow=~0UL-350;panelColor(0,255,0);clockNow=349;updateStatusAnimation();assert(!statusAnimating);
 for(int i=0;i<42;i++)assert(panelPixel.getPixelColor(i)==0x00FF00);
 panelOff();
 std::cout<<"Firmware scanner, debounce, watchdog and disarm checks passed\\n";
}
''')
            flags = []
            if sys.platform == "darwin":
                sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
                flags = ["-isysroot", sdk, "-isystem", str(Path(sdk) / "usr/include/c++/v1")]
            subprocess.run(["clang++", "-std=c++17", *flags, "-I", str(work), str(work / "checks.cpp"), "-o", str(work / "checks")], check=True)
            subprocess.run([str(work / "checks")], check=True)


if __name__ == "__main__":
    unittest.main()
