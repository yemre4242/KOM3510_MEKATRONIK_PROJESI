#include <Wire.h> 
#include <LiquidCrystal_I2C.h>
#include <Servo.h>

// --- Pin Tanımlamaları ---
const int trigPin = 4;
const int echoPin = 5;
Servo servo_giris;
Servo servo_cikis;
LiquidCrystal_I2C lcd(0x27, 16, 2);  

// --- Değişkenler ---
long sure;
int mesafe;
int sayac = 0;      
const int maxKapasite = 4;

String sonOkunanPlaka = "";
bool plakaBekleniyor = false; 

// --- Sınır Ayarları ---
int sinir_alt = 10; 
int sinir_ust = 30; 

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(10); 
  
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  

  servo_giris.attach(10, 500, 2500);
  servo_cikis.attach(9, 500, 2500);

  // Başlangıç Pozisyonları
  servo_giris.write(180); 
  servo_cikis.write(90);  

  lcd.init();      
  lcd.backlight();
  lcd.clear();
  lcd.print("Sistem Hazir");
  delay(1000);
}

void loop() {
  // --- 1. Mesafe Ölçümü ---
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  sure = pulseIn(echoPin, HIGH);
  mesafe = sure * 0.034 / 2;

  // --- 2. Python'dan Veri Dinleme ---
  if (Serial.available() > 0) {
    sonOkunanPlaka = Serial.readStringUntil('\n');
    sonOkunanPlaka.trim();
    
    if (sonOkunanPlaka.length() > 3) { 
      plakaBekleniyor = true; 
      lcd.clear();
      lcd.print("PLAKA ALINDI:");
      lcd.setCursor(0,1);
      lcd.print(sonOkunanPlaka);
    }
  }

  // --- 3. Bariyer ve Kontrol Mantığı ---

  // DURUM: GİRİŞ 
  if (mesafe > 0 && mesafe < sinir_alt) {
    if (plakaBekleniyor) {
      if (sayac >= maxKapasite) {
        lcd.clear();
        lcd.print("OTOPARK DOLU");
        delay(2000);
        plakaBekleniyor = false; 
      } else {
        sayac++;
        // Python'a log gönder: ISLEM:PLAKA
        Serial.print("GIRIS:"); 
        Serial.println(sonOkunanPlaka);
        
        lcd.clear();
        lcd.print("GIRIS ONAYLANDI");
        lcd.setCursor(0,1);
        lcd.print(sonOkunanPlaka);
        
        servo_giris.write(90); 
        delay(4000);           
        servo_giris.write(180); 
        
        plakaBekleniyor = false;
        sonOkunanPlaka = "";
        lcd.clear();
      }
    }
  } 
  
  // DURUM: ÇIKIŞ
  else if (mesafe >= sinir_alt && mesafe < sinir_ust) {
    if (plakaBekleniyor) {
      if (sayac > 0) sayac--;
      
      Serial.print("CIKIS:"); 
      Serial.println(sonOkunanPlaka);
      
      lcd.clear();
      lcd.print("GULE GULE");
      lcd.setCursor(0,1);
      lcd.print(sonOkunanPlaka);
      
      servo_cikis.write(180); 
      delay(4000);
      servo_cikis.write(90);  
      
      plakaBekleniyor = false;
      sonOkunanPlaka = "";
      lcd.clear();
    }
  }

  // DURUM: BOŞTA 
  else {

    servo_giris.write(180);
    servo_cikis.write(90);

    lcd.setCursor(0,0);
    lcd.print("Arac Sayisi: ");
    lcd.print(sayac);
    lcd.print("  ");
    
    lcd.setCursor(0,1);
    if(plakaBekleniyor) {
      lcd.print("BARIYERE YANAS ");
    } else {
      lcd.print("Bos Yer: ");
      lcd.print(maxKapasite - sayac);
      lcd.print("    ");
    }
  }

  delay(100); 
}