import os
import time
import cv2
import torch
import serial
import easyocr
import numpy as np
import re
from collections import Counter
from ultralytics import YOLO
from datetime import datetime  

# =============================================================================
# 1. AYARLAR & KONFİGÜRASYON
# =============================================================================
VIDEO_SOURCE = "http://**.**.**.***:4747/video" 
MODEL_PATH = "engineler/best.engine"       
YEDEK_MODEL = "ptler/best3.pt"
KAYIT_KLASORU = "yakalanan_plakalar"
LOG_DOSYASI = "otopark_kayitlari.txt" 
CONF_THRESHOLD = 0.50             

OKUMA_LIMITI = 12  
PLAKA_MAX_FRAME = 30 

ARDUINO_PORT = 'COM3'  #arduinonun takılı olduğu porta göre değiştirilmeli         
BAUD_RATE = 9600

# =============================================================================
# 2. BAŞLATMA
# =============================================================================
os.makedirs(KAYIT_KLASORU, exist_ok=True)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"✅ Sistem {device} modunda çalışıyor.")

reader = easyocr.Reader(["en"], gpu=(device == "cuda")) 

arduino = None
try:
    arduino = serial.Serial(port=ARDUINO_PORT, baudrate=BAUD_RATE, timeout=.1)
    print(f"✅ Arduino Bağlantısı Başarılı: {ARDUINO_PORT}")
    time.sleep(2) 
except Exception as e:
    print(f"⚠️ Arduino Bağlanamadı: {e}")

model_file = MODEL_PATH if os.path.exists(MODEL_PATH) else YEDEK_MODEL
model = YOLO(model_file)

plaka_havuzu = {}       
islenen_track_idler = set() 

# =============================================================================
# 3. FONKSİYONLAR
# =============================================================================

def plaka_temizle_ve_dogrula(text):
    temiz = re.sub(r'[^A-Z0-9]', '', text.upper())
    if temiz.startswith("TR"): temiz = temiz[2:]
    if 5 <= len(temiz) <= 9:
        return temiz
    return None

def ocr_pre_process(img_np):
    img = cv2.resize(img_np, (320, 80), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    gray = cv2.filter2D(gray, -1, kernel)
    return gray

# =============================================================================
# 4. ANA DÖNGÜ
# =============================================================================
cap = cv2.VideoCapture(VIDEO_SOURCE)
print("\n🚀 Plaka Tanıma ve Loglama Başladı. Çıkmak için 'q' tuşuna basın.\n")

while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    # --- ARDUINO'DAN GELEN ONAYI DİNLE ---
    if arduino and arduino.in_waiting > 0:
        try:
            gelen_veri = arduino.readline().decode('utf-8').strip()
            if ":" in gelen_veri:
                islem, plaka = gelen_veri.split(":")
                zaman = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                log_satiri = f"[{zaman}] {islem} YAPILDI - Plaka: {plaka}\n"
                
                with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
                    f.write(log_satiri)
                print(f"📝 TXT KAYDEDİLDİ: {log_satiri.strip()}")
        except:
            pass

    # YOLO Takip
    results = model.track(frame, persist=True, verbose=False, tracker="bytetrack.yaml")
    
    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        confs = results[0].boxes.conf.cpu().numpy()

        for box, track_id, conf in zip(boxes, ids, confs):
            if track_id in islenen_track_idler: continue
            if conf < CONF_THRESHOLD: continue

            x1, y1, x2, y2 = box
            crop = frame[max(0,y1-5):min(frame.shape[0],y2+5), max(0,x1-10):min(frame.shape[1],x2+10)]
            if crop.size == 0: continue

            processed_crop = ocr_pre_process(crop)
            ocr_results = reader.readtext(processed_crop, detail=0)
            raw_text = "".join(ocr_results)
            temiz_plaka = plaka_temizle_ve_dogrula(raw_text)

            if temiz_plaka:
                if track_id not in plaka_havuzu: plaka_havuzu[track_id] = []
                plaka_havuzu[track_id].append(temiz_plaka)
                
                havuz_boyutu = len(plaka_havuzu[track_id])
                if havuz_boyutu >= OKUMA_LIMITI:
                    oylama = Counter(plaka_havuzu[track_id])
                    kesin_plaka, tekrar_sayisi = oylama.most_common(1)[0]
                    
                    if tekrar_sayisi >= (OKUMA_LIMITI // 2):
                        print(f"🎯 KESİNLEŞTİ: {kesin_plaka} (ID:{track_id})")
                        if arduino and arduino.is_open:
                            arduino.write(f"{kesin_plaka}\n".encode())
                        
                        cv2.imwrite(f"{KAYIT_KLASORU}/{kesin_plaka}.jpg", crop)
                        islenen_track_idler.add(track_id)
                        del plaka_havuzu[track_id]

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID:{track_id} Isleniyor", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("YTU Otopark Kontrol Sistemi", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()

if arduino: arduino.close()
