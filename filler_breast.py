import re
import os
import fitz # PyMuPDF
import datetime
import sys

# ******* 1. การนำเข้า (ใช้ Vosk แทน Whisper) *******
# ตรวจสอบว่าไฟล์ vosk_transcrib.py อยู่ในโฟลเดอร์เดียวกัน 
try:
    from vosk_transcrib_breast import transcribe_audio, MODEL_PATH, AUDIO_FILE 
except ImportError:
    print("Error: ไม่พบไฟล์ vosk_transcrib.py หรือไม่ได้กำหนด MODEL_PATH/AUDIO_FILE")
    # หากไม่สามารถนำเข้าได้ ให้หยุดการทำงาน
    sys.exit(1)

# =========================================================
# === 1. การตั้งค่า - ไฟล์และ Mapping (ใช้ข้อความ Anchor) ===
# =========================================================

PDF_IN = r"Breast_gross_form_onepage.pdf"
# สร้างชื่อไฟล์เอาต์พุตที่มี Time Stamp 
PDF_OUT = "Breast_gross_form_onepag_filled.pdf" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".pdf"

# =========================================================
# === 2. ฟังก์ชันวิเคราะห์ข้อความ (Parsing) === 
# (ส่วนนี้ใช้ได้แล้ว จึงคงไว้ตามเดิม)
# =========================================================

def parse_transcribed_text(transcript):
    # 2.0 ทำความสะอาดข้อความ (รวมถึงการแปลง 'point' และ 'by' เป็นสัญลักษณ์)
    transcript_cleaned = transcript.lower().replace(" point ", ".").replace(" by ", " x ")

    # -- 2a) PARSE CHOICES --
    def pick_one(options):
        for opt in options:
            if re.search(rf"\b{re.escape(opt)}\b", transcript_cleaned):
                return opt
        return None

    choices_to_find = []
    for group in [
        ["previously opened"], ["right", "left"], ["radical", "total", "partial"],
        ["attached", "separated"], ["homogeneous", "inhomogeneous"], 
        ["well-defined", "ill-defined", "well - defined", "ill - defined"],
        ["papillary", "cauliflower", "well-encapsulated", "well - encapsulated"],
        ["soft", "firm", "hard"],
        ["white", "yellow", "brown", "grey", "tan", "grey-tan", "grey-white", "dark brown"],
    ]:
        val = pick_one(group)
        if val:
            choices_to_find.append(val.replace(" - ", "-"))

    if "with" in transcript_cleaned and ("focal hemorrhage" in transcript_cleaned or "focal necrosis" in transcript_cleaned):
        choices_to_find.append("with")
        if "focal hemorrhage" in transcript_cleaned: choices_to_find.append("focal hemorrhage")
        if "focal necrosis" in transcript_cleaned: choices_to_find.append("focal necrosis")
    elif "without" in transcript_cleaned:
        choices_to_find.append("without")

    seen = set()
    targets = [x for x in choices_to_find if not (x in seen or seen.add(x))]
    
    # -- 2b) PARSE DIMENSIONS --
    # 1. Specimen
    m_specimen = re.search(r"specimen measuring\s*([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)", transcript_cleaned)
    specimen_dims = m_specimen.groups() if m_specimen else None

    # 2. Kidney
    m_kidney = re.search(r"kidney measures\s*([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)", transcript_cleaned)
    kidney_dims = m_kidney.groups() if m_kidney else None
    
    # 3. Ureter
    m_ureter = re.search(r"ureter measures\s*([\d.]+).*?in length(?:\s*and\s*([\d.]+))?", transcript_cleaned)
    if m_ureter and not m_ureter.group(2):
        m2 = re.search(r"in length\s*and\s*([\d.]+)", transcript_cleaned)
        ureter_vals = (m_ureter.group(1), m2.group(1) if m2 else None)
    elif m_ureter:
        ureter_vals = (m_ureter.group(1), m_ureter.group(2))
    else:
        ureter_vals = None

    # 4. Surgical Number
    m_surgical = re.search(r"(?:surgical|specimen)\s+(?:number|id)\s+(?:is|number)\s*(\d+)", transcript_cleaned)
    surgical_number = m_surgical.group(1) if m_surgical else ""
    
    return {
        'targets_to_circle': targets,
        'surgical_number': surgical_number,
        'specimen_dims': specimen_dims,
        'kidney_dims': kidney_dims,
        'ureter_vals': ureter_vals,
    }


# =========================================================
# === 3. ฟังก์ชัน Helpers สำหรับ PyMuPDF (fitz) === 
# =========================================================

def write_after_anchor(page, anchor_text_list, to_write, dx=6, dy=-2, box_width=260, fontsize=10):
    """
    ค้นหา 'anchor_text' (สามารถเป็น List ของตัวเลือกได้) แล้ววาด 'to_write' ลงในกล่องข้อความที่กำหนด
    """
    # ทำให้ anchor_text_list เป็น List เสมอ
    if isinstance(anchor_text_list, str):
        anchor_text_list = [anchor_text_list]
        
    for anchor_text in anchor_text_list:
        hits = page.search_for(anchor_text)
        if hits:
            anchor = hits[0] 
            x_start = anchor.x1 + dx
            # สร้าง Rect สำหรับกล่องข้อความ
            rect = fitz.Rect(x_start, anchor.y0 - 2, x_start + box_width, anchor.y1 + 10) 
            page.insert_textbox(rect, to_write, fontsize=fontsize, fontname="helv", color=(0, 0, 0), align=0)
            print(f"[write] FOUND anchor '{anchor_text}' -> Wrote '{to_write}'")
            return True # คืนค่า True ทันทีที่เขียนสำเร็จ
            
    print(f"❌ Anchor not found after searching: {anchor_text_list}. Cannot write data: '{to_write}'")
    return False

def circle_word(page, word, max_hits=1):
    # (ฟังก์ชันนี้ใช้ได้แล้ว จึงคงไว้ตามเดิม)
    hits = page.search_for(word)
    count = 0
    for rect in hits:
        pad = 1.5
        rect = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
        shape = page.new_shape()
        shape.draw_oval(rect)
        shape.finish(color=(1, 0, 0), width=1.5)
        shape.commit()
        count += 1
        if count >= max_hits: break
    if count == 0: print(f"⚠ Word '{word}' not found on page.")
    return count

# =========================================================
# === 4. ฟังก์ชันหลักในการวาดข้อมูลลง PDF === (ใช้ PyMuPDF)
# =========================================================

def draw_data_on_pdf(input_pdf, output_pdf, parsed_data):
    
    if not os.path.exists(input_pdf):
        print(f"Error: Input PDF file not found at {input_pdf}")
        return
        
    doc = fitz.open(input_pdf)
    page = doc[0] 

    print("\n--- Starting PDF Drawing ---")

    # A. CIRCLE CHECKBOX WORDS (ทำเครื่องหมายตัวเลือก)
    print("\n--- Circling Checkbox/Radio Options ---")
    for t in parsed_data['targets_to_circle']:
        for q in (t, t.replace("-", " - ")):
            if circle_word(page, q, max_hits=1):
                break
        else:
            print(f"⚠ Not found on page: {t}")
            
    # B. FILL NUMBERS BY ANCHOR (กรอกข้อมูลตัวเลข)
    
    # 1. Surgical Number (ลองค้นหาหลายรูปแบบ)
    if parsed_data['surgical_number']:
        # ลองใช้ anchor หลายตัวเผื่อการพิมพ์ผิดใน template
        anchors = ["Surgical number:", "Surgical No:", "Specimen No:"]
        write_after_anchor(page, anchors, parsed_data['surgical_number'], dx=100, box_width=100)
        
    # 2. Specimen Dimensions 
    if parsed_data['specimen_dims']:
        dims_str = " x ".join(parsed_data['specimen_dims']) + " cm"
        # ลองค้นหา anchor หลายรูปแบบ
        anchors = ["specimen measuring", "specimen measures"]
        write_after_anchor(page, anchors, dims_str, dx=150, box_width=100)
    
    # 3. Kidney Dimensions 
    if parsed_data['kidney_dims']:
        dims_str = " x ".join(parsed_data['kidney_dims']) + " cm"
        # ลองค้นหา anchor ทั้งตัวใหญ่/เล็ก และรูปแบบอื่น
        anchors = ["The kidney measures", "the kidney measures", "kidney measures"]
        write_after_anchor(page, anchors, dims_str, dx=100, box_width=100)
            
    # 4. Ureter Length & Diameter 
    if parsed_data['ureter_vals']:
        # Length
        length_txt = parsed_data['ureter_vals'][0] + " cm"
        anchors_length = ["ureter measures", "The ureter measures"]
        write_after_anchor(page, anchors_length, length_txt, dx=100, box_width=50) 
        
        # Diameter 
        if parsed_data['ureter_vals'][1]:
            diam_txt = parsed_data['ureter_vals'][1] + " cm"
            anchors_diameter = ["in length and", "in length, and"]
            write_after_anchor(page, anchors_diameter, diam_txt, dx=10, box_width=50)
            
    # C. บันทึกไฟล์ใหม่
    doc.save(output_pdf)
    doc.close()
    print(f"\n✅ PDF Drawing Complete. New report saved as: {output_pdf}")


# =========================================================
# === 5. รันโปรแกรมหลัก ===
# =========================================================

if __name__ == "__main__":
    
    # 1. ถอดความเสียง (ใช้ Vosk)
    print("\n--- Starting Transcription (Vosk) ---")
    transcribed_text = transcribe_audio(MODEL_PATH, AUDIO_FILE)
    
    if transcribed_text.startswith("Error:"):
        print(f"\nFATAL ERROR: {transcribed_text}")
    else:
        print("\n====================================")
        print("✅ TRANSCRIPTION COMPLETE (Vosk)")
        print("====================================")
        print("[Vosk Transcribed Text]:", transcribed_text)
        
        # 2. วิเคราะห์ข้อความ
        parsed_data = parse_transcribed_text(transcribed_text)
        
        print("\n[PARSED DATA]:", parsed_data)
        
        # 3. วาดข้อมูลลง PDF
        draw_data_on_pdf(PDF_IN, PDF_OUT, parsed_data)