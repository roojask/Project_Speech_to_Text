import re
import json
import wave
import fitz
import numpy as np
import soundfile as sf
from vosk import Model, KaldiRecognizer

# =========================
# CONSTANT
# =========================
CM = 28.35  # 1 cm in PDF point

# =========================
# PATH CONFIG
# =========================
AUDIO = "input_Breast.wav"
VOSK_MODEL = r"C:\Users\HP\Downloads\ProjectSound\vosk-model-en-us-0.22"

PDF_IN = "Breast_gross_form_onepage.pdf"
PDF_OUT = "Breast_gross_form_onepag_filled_2.pdf"

# =========================
# AUDIO PREP
# =========================
def prepare_audio(inp, out="temp.wav"):
    data, sr = sf.read(inp)
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    sf.write(out, data, 16000)
    return out

# =========================
# TRANSCRIBE
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
# NORMALIZE
# =========================
NUM_WORDS = {
    "zero":"0","one":"1","two":"2","three":"3","four":"4",
    "five":"5","six":"6","seven":"7","eight":"8","nine":"9",
    "ten":"10","point":"."
}

def normalize(t):
    for k, v in NUM_WORDS.items():
        t = re.sub(rf"\b{k}\b", v, t)
    return re.sub(r"\s+", " ", t)

# =========================
# PARSE
# =========================
def parse_breast(t):
    d = {
        "side": None,
        "procedure": None,
        "nipple": None,
        "quadrant_vert": None,
        "quadrant_hori": None,
        "specimen": None,
        "skin": None,
        "mass_dim": None,
    }

    if "right" in t: d["side"] = "right"
    if "left" in t: d["side"] = "left"

    if "modified radical mastectomy" in t:
        d["procedure"] = "modified radical"
    elif "simple mastectomy" in t:
        d["procedure"] = "simple"

    if "nipple is inverted" in t:
        d["nipple"] = "inverted"
    elif "nipple is everted" in t or "nipple is normal" in t:
        d["nipple"] = "normal"

    if "upper" in t: d["quadrant_vert"] = "upper"
    if "lower" in t: d["quadrant_vert"] = "lower"
    if "inner" in t: d["quadrant_hori"] = "inner"
    if "outer" in t: d["quadrant_hori"] = "outer"

    m = re.search(r"measuring ([\d.]+) by ([\d.]+) by ([\d.]+)", t)
    if m: d["specimen"] = m.groups()

    m = re.search(r"skin.*?([\d.]+) by ([\d.]+)", t)
    if m: d["skin"] = m.groups()

    m = re.search(r"mass.*?([\d.]+) by ([\d.]+) by ([\d.]+)", t)
    if m: d["mass_dim"] = m.groups()

    return d

# =========================
# PDF HELPERS
# =========================
def circle_word(page, word):
    """ใช้กับข้อความธรรมดา"""
    if not word:
        return
    hits = page.search_for(word)
    if not hits:
        return
    r = hits[0]
    r = fitz.Rect(r.x0-2, r.y0-2, r.x1+2, r.y1+2)
    s = page.new_shape()
    s.draw_oval(r)
    s.finish(color=(1,0,0), width=1.2)
    s.commit()

def tick_checkbox(page, x, y, size=12):
    """ใช้กับช่องสี่เหลี่ยม ☐"""
    page.insert_text(
        fitz.Point(x, y),
        "/",
        fontsize=size,
        fontname="helv"
    )

def write_numbers_at(page, start_x, y, numbers, step_cm=1, fontsize=10):
    """วางตัวเลขตรงช่องจุดไข่ปลา"""
    x = start_x
    step = step_cm * CM
    for n in numbers:
        page.insert_text(
            fitz.Point(x, y),
            n,
            fontsize=fontsize
        )
        x += step

# =========================
# CHECKBOX COORDINATES (ปรับได้)
# =========================
CHECKBOX = {
    "right": (210, 720),
    "left": (245, 720),

    "modified radical": (180, 700),
    "simple": (180, 675),

    "nipple_normal": (130, 585),
    "nipple_inverted": (190, 585),

    "upper": (250, 515),
    "lower": (290, 515),
    "inner": (330, 515),
    "outer": (370, 515),

    "mass": (70, 470),
}

# =========================
# NUMBER FIELD POSITIONS
# =========================
NUMBER_POS = {
    "specimen": (230, 690),
    "skin": (250, 655),
    "mass": (260, 465),
}

# =========================
# MAIN
# =========================
wav = prepare_audio(AUDIO)
txt = normalize(transcribe(wav))
data = parse_breast(txt)

doc = fitz.open(PDF_IN)
page = doc[0]

# ---- checkbox tick ----
if data["side"]:
    tick_checkbox(page, *CHECKBOX[data["side"]])

if data["procedure"]:
    tick_checkbox(page, *CHECKBOX[data["procedure"]])

if data["nipple"] == "normal":
    tick_checkbox(page, *CHECKBOX["nipple_normal"])
elif data["nipple"] == "inverted":
    tick_checkbox(page, *CHECKBOX["nipple_inverted"])

if data["quadrant_vert"]:
    tick_checkbox(page, *CHECKBOX[data["quadrant_vert"]])
if data["quadrant_hori"]:
    tick_checkbox(page, *CHECKBOX[data["quadrant_hori"]])

if data["mass_dim"]:
    tick_checkbox(page, *CHECKBOX["mass"])

# ---- numbers (absolute position) ----
if data["specimen"]:
    write_numbers_at(page, *NUMBER_POS["specimen"], data["specimen"], step_cm=1)

if data["skin"]:
    write_numbers_at(page, *NUMBER_POS["skin"], data["skin"], step_cm=1)

if data["mass_dim"]:
    write_numbers_at(page, *NUMBER_POS["mass"], data["mass_dim"], step_cm=1)

doc.save(PDF_OUT)
doc.close()

print("✅ PDF completed →", PDF_OUT)
