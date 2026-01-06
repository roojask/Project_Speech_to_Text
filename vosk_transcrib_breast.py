import wave
import json
import os
from vosk import Model, KaldiRecognizer, SetLogLevel

# =========================================================
# === 1. การตั้งค่า - กรุณาแก้ไขส่วนนี้ก่อนใช้งาน ===
# =========================================================

# 1.1 ตั้งค่าเส้นทางไปยังโฟลเดอร์โมเดล Vosk
# ตัวอย่าง: "C:/Users/YourName/Desktop/vosk-model-en-us-0.42-gigaspeech"
# หรือสำหรับ Linux/Mac: "vosk-model-en-us-0.42-gigaspeech"
MODEL_PATH = "C:/Users/HP/Downloads/ProjectSound/vosk-model-en-us-0.22"

# 1.2 ตั้งค่าชื่อไฟล์เสียงที่คุณต้องการแปลง (ต้องเป็น .wav และ 16kHz Mono)
AUDIO_FILE = "input_Breast.wav"              

# ปิดข้อความเตือนของ Vosk เพื่อให้ผลลัพธ์สะอาดตา
SetLogLevel(0) 

# =========================================================
# === 2. ฟังก์ชันหลักในการถอดความเสียง ===
# =========================================================

def transcribe_audio(model_path, audio_file):
    """
    ทำการแปลงไฟล์เสียง WAV ให้เป็นข้อความโดยใช้ Vosk
    """
    
    # ตรวจสอบว่าไฟล์โมเดลและไฟล์เสียงมีอยู่จริง
    if not os.path.exists(model_path):
        return f"Error: Model path not found at {model_path}"
    if not os.path.exists(audio_file):
        return f"Error: Audio file not found at {audio_file}"

    # 2.1 โหลดโมเดล Vosk
    try:
        print(f"Loading Vosk model from: {model_path}...")
        model = Model(model_path)
    except Exception as e:
        return f"Error loading model: {e}"

    # 2.2 เปิดไฟล์เสียง WAV และตรวจสอบคุณสมบัติ
    try:
        wf = wave.open(audio_file, "rb")
    except Exception as e:
        return f"Error opening audio file: {e}"

    # ตรวจสอบคุณสมบัติไฟล์ WAV ที่เหมาะสม
    if wf.getnchannels() != 1 or wf.getframerate() != 16000:
        print("--- ⚠️ คำเตือน ---")
        print("Vosk ทำงานได้ดีที่สุดกับไฟล์เสียงแบบ Mono (1 Channel) และ Sample Rate 16000 Hz.")
        print(f"ไฟล์ปัจจุบัน: Channels={wf.getnchannels()}, Rate={wf.getframerate()} Hz")
        print("อาจมีผลต่อความแม่นยำ หากไฟล์ของคุณไม่ตรงตามข้อกำหนด")
        print("------------------")
        # โค้ดจะยังคงทำงานต่อ แต่ผลลัพธ์อาจไม่ดีที่สุด

    # 2.3 สร้าง Recognizer
    # โค้ดนี้จะใช้ Sample Rate ของไฟล์ WAV
    rec = KaldiRecognizer(model, wf.getframerate())

    # 2.4 ประมวลผลและถอดความเสียง
    full_text = []
    print("Starting transcription...")
    
    while True:
        # อ่านไฟล์เสียงเป็นส่วนๆ (Chunk size: 4000 frames)
        data = wf.readframes(4000) 
        if len(data) == 0:
            break
        
        # ส่งข้อมูลเสียงไปยัง Vosk
        if rec.AcceptWaveform(data):
            # ดึงผลลัพธ์แบบเต็มประโยคออกมา (ถ้ามี)
            result = json.loads(rec.Result())
            full_text.append(result.get("text", ""))

    # 2.5 รับผลลัพธ์สุดท้าย (สำหรับข้อมูลที่ค้างอยู่ใน Buffer)
    final_result = json.loads(rec.FinalResult())
    full_text.append(final_result.get("text", ""))

    # ปิดไฟล์
    wf.close()
    
    # รวมข้อความทั้งหมดเข้าด้วยกัน
    transcribed_text = ' '.join(full_text).strip()
    return transcribed_text

# =========================================================
# === 3. การใช้งานโค้ดและแสดงผล ===
# =========================================================

if __name__ == "__main__":
    
    # เรียกใช้ฟังก์ชันแปลงเสียง
    result_text = transcribe_audio(MODEL_PATH, AUDIO_FILE)
    
    print("\n====================================")
    print("✅ ผลลัพธ์การถอดความเสียง (Transcribed Text)")
    print("====================================")
    
    if result_text.startswith("Error:"):
        print(result_text)
    else:
        # นี่คือข้อความที่คุณจะใช้กรอกในแบบฟอร์ม
        print(result_text)
        
        # ตัวอย่าง: การนำข้อความไปใช้ในขั้นตอนต่อไป
        print("\n--- ขั้นตอนต่อไป ---")
        print("ข้อความนี้สามารถนำไปใช้กับไลบรารี PyAutoGUI (สำหรับการวางข้อความ) หรือ Selenium (สำหรับการกรอกแบบฟอร์มเว็บไซต์) ได้")
        
        # หากคุณต้องการนำไปคัดลอกลงในคลิปบอร์ด
        # import pyperclip
        # pyperclip.copy(result_text)
        # print("ข้อความถูกคัดลอกไปยังคลิปบอร์ดแล้ว")
        
    print("====================================")