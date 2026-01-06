from pydub import AudioSegment
import os

# =========================================================
# === 1. การตั้งค่า - กรุณาแก้ไขส่วนนี้ ===
# =========================================================

# 1.1 ชื่อไฟล์เสียงต้นฉบับ (รองรับ MP3, WAV, AAC ฯลฯ)
INPUT_FILE_NAME = "Breast gross 1.mp3"  # <--- แก้ไขชื่อไฟล์ต้นฉบับของคุณ
# 1.2 ชื่อไฟล์ WAV ที่แปลงเสร็จแล้ว (จะใช้ใน Vosk)
OUTPUT_FILE_NAME = "input_Breast.wav" 

# =========================================================
# === 2. ฟังก์ชันหลักในการแปลงไฟล์ ===
# =========================================================

def convert_audio_for_vosk(input_path, output_path):
    """
    แปลงไฟล์เสียงให้เป็น WAV, 16000 Hz, Mono 16-bit
    """
    print(f"Loading input file: {input_path}")
    
    # 1. โหลดไฟล์เสียง
    # Pydub จะอนุมานรูปแบบไฟล์จากนามสกุล (เช่น .mp3, .wav)
    try:
        # ตรวจสอบนามสกุลไฟล์
        file_ext = os.path.splitext(input_path)[1].lower().replace('.', '')
        if not file_ext:
            print("Error: Input file must have a file extension (e.g., .mp3, .wav)")
            return
            
        audio = AudioSegment.from_file(input_path, format=file_ext)
        print(f"Original: Channels={audio.channels}, Rate={audio.frame_rate} Hz")
        
    except Exception as e:
        print(f"Error loading audio file. Check if FFmpeg is installed and accessible in your path.")
        print(f"Details: {e}")
        return

    # 2. แปลง Channels (Mono)
    if audio.channels > 1:
        audio = audio.set_channels(1) # ตั้งค่าให้เป็น Mono
        print("Converted to: Mono (1 Channel)")
    
    # 3. แปลง Sample Rate (16000 Hz)
    if audio.frame_rate != 16000:
        audio = audio.set_frame_rate(16000) # ตั้งค่า Sample Rate เป็น 16000 Hz
        print("Converted to: 16000 Hz Sample Rate")

    # 4. ส่งออกเป็นไฟล์ WAV
    # ใช้ 16-bit PCM ซึ่งเป็นค่ามาตรฐาน
    audio.export(output_path, format="wav")
    print(f"\n✅ Conversion Complete. New file saved as: {output_path}")

# =========================================================
# === 3. การใช้งานโค้ด ===
# =========================================================

if __name__ == "__main__":
    # ตรวจสอบว่าไฟล์ต้นฉบับมีอยู่จริงก่อนเริ่ม
    if not os.path.exists(INPUT_FILE_NAME):
        print(f"Error: Input file '{INPUT_FILE_NAME}' not found in the current directory.")
    else:
        convert_audio_for_vosk(INPUT_FILE_NAME, OUTPUT_FILE_NAME)
        
    print("\n--- ขั้นตอนต่อไป ---")
    print(f"คุณสามารถรัน vosk_transcribe.py โดยใช้ไฟล์ '{OUTPUT_FILE_NAME}' ได้เลย")