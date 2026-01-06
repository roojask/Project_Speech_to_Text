import re
import json
import wave
import fitz  # PyMuPDF
from vosk import Model, KaldiRecognizer

# -----------------------------
# CONFIG
# -----------------------------
AUDIO = "input_Breast.wav"
VOSK_MODEL = r"C:\Users\HP\Downloads\ProjectSound\vosk-model-en-us-0.22"

PDF_IN = "Breast_gross_form_onepage.pdf"
PDF_OUT = "Breast_gross_form_onepag_filled.pdf"

# -----------------------------
# NUMBER WORDS → DIGITS
# -----------------------------
NUM_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16",
    "seventeen": "17", "eighteen": "18", "nineteen": "19",
    "twenty": "20"
}

def words_to_numbers(text):
    # two point eight → 2.8
    text = re.sub(
        r"\b(\w+)\s+point\s+(\w+)\b",
        lambda m: NUM_WORDS.get(m.group(1), m.group(1)) + "." +
                  NUM_WORDS.get(m.group(2), m.group(2)),
        text
    )
    # eighteen → 18
    for w, n in NUM_WORDS.items():
        text = re.sub(rf"\b{w}\b", n, text)
    return text

# -----------------------------
# 1) TRANSCRIBE (VOSK)
# -----------------------------
print("Transcribing audio with Vosk…")

model = Model(VOSK_MODEL)
wf = wave.open(AUDIO, "rb")

if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
    raise ValueError("Audio must be WAV mono PCM 16kHz")

rec = KaldiRecognizer(model, wf.getframerate())
rec.SetWords(True)

texts = []

while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    if rec.AcceptWaveform(data):
        res = json.loads(rec.Result())
        texts.append(res.get("text", ""))

final_res = json.loads(rec.FinalResult())
texts.append(final_res.get("text", ""))

raw_transcript = " ".join(texts).lower()
transcript = words_to_numbers(raw_transcript)

print("Transcript (normalized):\n", transcript[:300], "...\n")

# -----------------------------
# 2) PARSE CHOICES
# -----------------------------
def pick_one(options):
    for opt in options:
        if re.search(rf"\b{re.escape(opt)}\b", transcript):
            return opt
    return None

choices_to_find = []
for group in [
    ["previously opened"],
    ["right", "left"],
    ["radical", "total", "partial"],
    ["attached", "separated"],
    ["homogeneous", "inhomogeneous"],
    ["well-defined", "ill-defined", "well - defined", "ill - defined"],
    ["papillary", "cauliflower", "well-encapsulated", "well - encapsulated"],
    ["soft", "firm", "hard"],
    ["white", "yellow", "brown", "grey", "tan", "grey-tan", "grey-white", "dark brown"],
]:
    val = pick_one(group)
    if val:
        choices_to_find.append(val.replace(" - ", "-"))

seen = set()
targets = [x for x in choices_to_find if not (x in seen or seen.add(x))]
print("Targets to circle:", targets)

# -----------------------------
# 2b) PARSE SPECIMEN DIMENSIONS
# -----------------------------
m = re.search(
    r"specimen measuring\s+([\d.]+)\s*by\s*([\d.]+)\s*by\s*([\d.]+)",
    transcript
)
specimen_dims = m.groups() if m else None
print("Specimen:", specimen_dims)

# -----------------------------
# 3) OPEN PDF
# -----------------------------
doc = fitz.open(PDF_IN)
page = doc[0]

# -----------------------------
# HELPERS
# -----------------------------
def circle_word(page, word, max_hits=1):
    hits = page.search_for(word)
    count = 0
    for rect in hits:
        pad = 1.5
        rect = fitz.Rect(rect.x0 - pad, rect.y0 - pad,
                          rect.x1 + pad, rect.y1 + pad)
        shape = page.new_shape()
        shape.draw_oval(rect)
        shape.finish(color=(1, 0, 0), width=1.5)
        shape.commit()
        count += 1
        if count >= max_hits:
            break
    return count

def write_after_any_anchor(page, anchor_list, to_write,
                           dx=6, box_width=260, fontsize=10):
    for anchor_text in anchor_list:
        hits = page.search_for(anchor_text)
        if hits:
            anchor = hits[0]
            rect = fitz.Rect(
                anchor.x1 + dx,
                anchor.y0 - 2,
                anchor.x1 + dx + box_width,
                anchor.y1 + 10
            )
            page.insert_textbox(
                rect,
                to_write,
                fontsize=fontsize,
                fontname="helv",
                color=(0, 0, 0)
            )
            print(f"[write] after '{anchor_text}' -> {to_write}")
            return True
    print(f"⚠ Anchors not found: {anchor_list}")
    return False

# -----------------------------
# 3a) CIRCLE CHECKBOX WORDS
# -----------------------------
for t in targets:
    for q in (t, t.replace("-", " - ")):
        if circle_word(page, q):
            break

# -----------------------------
# 3b) FILL SPECIMEN SIZE
# -----------------------------
if specimen_dims:
    write_after_any_anchor(
        page,
        ["specimen measuring", "measuring"],
        " x ".join(specimen_dims) + " cm"
    )

# -----------------------------
# SAVE
# -----------------------------
doc.save(PDF_OUT)
doc.close()

print(f"✅ Done -> {PDF_OUT}")
