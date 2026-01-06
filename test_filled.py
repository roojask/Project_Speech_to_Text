import re
import json
import wave
import fitz  # PyMuPDF
import numpy as np
import soundfile as sf
from vosk import Model, KaldiRecognizer

# =========================
# PATH CONFIG
# =========================
AUDIO = "input_Breast.wav"
VOSK_MODEL = r"C:\Users\HP\Downloads\ProjectSound\vosk-model-en-us-0.22"

PDF_IN = "Breast_gross_form_onepage.pdf"
PDF_OUT = "Breast_gross_form_onepag_filled.pdf"

# =========================
# AUDIO PREP
# =========================
def prepare_audio(inp, out="temp.wav"):
    data, sr = sf.read(inp)
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
    sf.write(out, data, 16000)
    return out

# =========================
# TRANSCRIBE (VOSK)
# =========================
def transcribe(audio):
    wf = wave.open(audio, "rb")
    rec = KaldiRecognizer(Model(VOSK_MODEL), wf.getframerate())
    rec.SetWords(True)

    res = []
    while True:
        d = wf.readframes(4000)
        if len(d) == 0:
            break
        if rec.AcceptWaveform(d):
            res.append(json.loads(rec.Result()))
    res.append(json.loads(rec.FinalResult()))
    wf.close()

    return " ".join(r.get("text", "") for r in res).lower()

# =========================
# NORMALIZE TEXT
# =========================
NUM_WORDS = {
    "zero":"0","one":"1","two":"2","three":"3","four":"4",
    "five":"5","six":"6","seven":"7","eight":"8","nine":"9",
    "ten":"10","eleven":"11","twelve":"12","thirteen":"13",
    "fourteen":"14","fifteen":"15","sixteen":"16",
    "seventeen":"17","eighteen":"18","nineteen":"19",
    "twenty":"20",
    "point":"."
}

def normalize(t):
    for k, v in NUM_WORDS.items():
        t = re.sub(rf"\b{k}\b", v, t)

    # FIX: ต้องใส่ t
    t = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", t)

    t = t.replace("centimetres", "cm").replace("centimeters", "cm")
    t = re.sub(r"\s+", " ", t)
    return t
# =========================
# PARSE BREAST DATA
# =========================
def parse_breast(t):
    d = {
        "side": None,
        "procedure": None,
        "specimen": None,
        "skin": None,
        "nipple": None,
        "mass_dim": None,
        "mass_color": []
    }

    if re.search(r"\bright\b|\brt\b", t):
        d["side"] = "right"
    elif re.search(r"\bleft\b|\blt\b", t):
        d["side"] = "left"

    if "modified radical mastectomy" in t:
        d["procedure"] = "modified radical"

    m = re.search(r"specimen measuring ([\d.]+) by ([\d.]+) by ([\d.]+)", t)
    if m:
        d["specimen"] = m.groups()

    m = re.search(r"skin.*?([\d.]+) by ([\d.]+) cm", t)
    if m:
        d["skin"] = m.groups()

    if "nipple is inverted" in t or "nipple is averted" in t:
        d["nipple"] = "inverted"

    m = re.search(r"mass.*?([\d.]+) by ([\d.]+) by ([\d.]+)", t)
    if m:
        d["mass_dim"] = m.groups()

    for c in ["white", "yellow", "yellow-white", "grey", "tan"]:
        if c in t:
            d["mass_color"].append(c)

    return d

# =========================
# PDF HELPERS
# =========================
def circle_word(page, word):
    hits = page.search_for(word)
    if not hits:
        return False
    r = hits[0]
    pad = 1.5
    r = fitz.Rect(r.x0-pad, r.y0-pad, r.x1+pad, r.y1+pad)
    s = page.new_shape()
    s.draw_oval(r)
    s.finish(color=(1,0,0), width=1.5)
    s.commit()
    return True

def write_after(page, x, y, text):
    rect = fitz.Rect(x, y, x + 200, y + 12)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv")

# =========================
# ⚠️ ABSOLUTE POSITIONS (ปรับครั้งเดียว ใช้ยาว)
# =========================
POS = {
    "mass_size": (280, 420),      # 👈 ปรับตำแหน่งนี้ครั้งเดียว
    "specimen": (260, 190),
    "skin": (260, 220),
}

# =========================
# MAIN
# =========================
wav = prepare_audio(AUDIO)
txt = normalize(transcribe(wav))

print("Transcript:\n", txt, "\n")

data = parse_breast(txt)
print("Parsed:", data)

doc = fitz.open(PDF_IN)
page = doc[0]

# circle checkboxes (ถ้ามี text)
circle_word(page, "Right")
circle_word(page, "Modified radical mastectomy")
circle_word(page, "Inverted nipple")

# write numbers by position
if data["specimen"]:
    write_after(page, *POS["specimen"],
                " x ".join(data["specimen"]) + " cm")

if data["skin"]:
    write_after(page, *POS["skin"],
                " x ".join(data["skin"]) + " cm")

if data["mass_dim"]:
    write_after(page, *POS["mass_size"],
                " x ".join(data["mass_dim"]) + " cm")

doc.save(PDF_OUT)
doc.close()

print(f"✅ PDF Drawing Complete → {PDF_OUT}")
