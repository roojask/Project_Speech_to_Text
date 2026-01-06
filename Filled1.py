import re
import json
import wave
import fitz
import numpy as np
import soundfile as sf
from vosk import Model, KaldiRecognizer

# =========================
# PATH CONFIG
# =========================
AUDIO = "input_Breast.wav"
VOSK_MODEL = r"C:\Users\HP\Downloads\ProjectSound\vosk-model-en-us-0.22"

PDF_IN = "Breast_gross_form_onepage.pdf"
PDF_OUT = "Breast_gross_form_onepag_filled_1.pdf"

CM = 28.35  # 1 cm in PDF point

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
    "ten":"10","eleven":"11","twelve":"12","thirteen":"13",
    "fourteen":"14","fifteen":"15","sixteen":"16",
    "seventeen":"17","eighteen":"18","nineteen":"19",
    "twenty":"20","point":"."
}

def normalize(t):
    for k, v in NUM_WORDS.items():
        t = re.sub(rf"\b{k}\b", v, t)
    t = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", t)
    t = t.replace("centimeters", "cm").replace("centimetres", "cm")
    return re.sub(r"\s+", " ", t)

# =========================
# PARSE
# =========================
def parse_breast(t):
    d = {
        "side": None,
        "procedure": None,
        "specimen": None,
        "skin": None,
        "nipple": None,
        "mass_dim": None,
        "quadrant_vert": None,
        "quadrant_hori": None,
        "margins": {},
        "mass_color": []
    }

    if "right" in t: d["side"] = "right"
    if "left" in t: d["side"] = "left"

    if "modified radical mastectomy" in t:
        d["procedure"] = "modified radical"
    elif "simple mastectomy" in t:
        d["procedure"] = "simple"

    m = re.search(r"measuring ([\d.]+) by ([\d.]+) by ([\d.]+)", t)
    if m: d["specimen"] = m.groups()

    m = re.search(r"skin.*?([\d.]+) by ([\d.]+) cm", t)
    if m: d["skin"] = m.groups()

    if "nipple is inverted" in t or "nipple is averted" in t:
        d["nipple"] = "inverted"
    elif "nipple is everted" in t or "nipple is normal" in t:
        d["nipple"] = "normal"

    m = re.search(r"mass.*?([\d.]+) by ([\d.]+) by ([\d.]+)", t)
    if m: d["mass_dim"] = m.groups()

    if "upper" in t: d["quadrant_vert"] = "upper"
    if "lower" in t: d["quadrant_vert"] = "lower"
    if "inner" in t: d["quadrant_hori"] = "inner"
    if "outer" in t: d["quadrant_hori"] = "outer"

    for k in ["deep","superior","inferior","medial","lateral","skin"]:
        m = re.search(rf"([\d.]+) cm from {k}", t)
        if m: d["margins"][k] = m.group(1)

    return d

# =========================
# PDF HELPERS
# =========================
def circle_word(page, word):
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

def write_numbers_spaced(page, anchor, dx, numbers, step_cm=1, fontsize=10):
    hits = page.search_for(anchor)
    if not hits:
        return

    r = hits[0]
    step = step_cm * CM
    x = r.x1 + dx

    for n in numbers:
        box = fitz.Rect(x, r.y0-2, x + 40, r.y1+8)
        page.insert_textbox(box, n, fontsize=fontsize, align=1)
        x += step

def write_margin(page, label, value):
    hits = page.search_for(f"cm. from {label} margin")
    if not hits:
        return
    r = hits[0]
    box = fitz.Rect(r.x0-60, r.y0-2, r.x0-5, r.y1+2)
    page.insert_textbox(box, value, fontsize=10, align=1)

# =========================
# MAIN
# =========================
LEFT_SHIFT = -CM  # ขยับซ้าย 1 เซน

wav = prepare_audio(AUDIO)
txt = normalize(transcribe(wav))
data = parse_breast(txt)

doc = fitz.open(PDF_IN)
page = doc[0]

circle_word(page, data["side"])
circle_word(page, data["procedure"])
circle_word(page, data["nipple"])
circle_word(page, data["quadrant_vert"])
circle_word(page, data["quadrant_hori"])

if data["specimen"]:
    write_numbers_spaced(page, "Measuring", 40 + LEFT_SHIFT, data["specimen"], step_cm=1)

if data["skin"]:
    write_numbers_spaced(page, "The skin ellipse", 40 + LEFT_SHIFT, data["skin"], step_cm=1)

if data["mass_dim"]:
    write_numbers_spaced(
        page,
        "infiltrative firm yellow white mass",
        40 + LEFT_SHIFT,
        data["mass_dim"],
        step_cm=1
    )

for k, v in data["margins"].items():
    write_margin(page, k, v)

doc.save(PDF_OUT)
doc.close()

print("✅ PDF completed →", PDF_OUT)
