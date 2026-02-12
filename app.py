import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import cv2
import numpy as np
import io
import re
import zipfile
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper
import pandas as pd

st.set_page_config(page_title="Paper + Seller System", layout="centered")
st.title("📄 Paper + Seller System")

# =========================
# SESSION INIT
# =========================
if "labels" not in st.session_state:
    st.session_state.labels = []

if "df" not in st.session_state:
    st.session_state.df = None

if "crop_box" not in st.session_state:
    st.session_state.crop_box = None

if "apply_all" not in st.session_state:
    st.session_state.apply_all = False

if "action" not in st.session_state:
    st.session_state.action = None

# =========================
# CONFIG
# =========================
PRODUCT_KEYWORDS = {
    "hoodie": ["hoodie"],
    "sweatshirt": ["sweatshirt"],
    "tshirt": ["tshirt", "t-shirt", "tee"],
    "cap": ["cap"],
    "balaclava ninja hoodie": ["balaclava"],
    "sherpa jacket": ["sherpa"],
    "leather jacket": ["leather"],
    "varsity jacket": ["varsity"]
}

SIZES = ["XXXL", "XXL", "XL", "L", "M", "S"]

# =========================
# HELPERS
# =========================
def preprocess(img):
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5,5), 0)
    gray = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    return gray

def detect_product(text):
    t = text.lower()
    for p, keys in PRODUCT_KEYWORDS.items():
        for k in keys:
            if k in t:
                return p
    return "Unknown"

def detect_size(text):
    t = text.upper()
    for s in SIZES:
        if re.search(rf"\b{s}\b", t):
            return s
    return "Unknown"

def extract_order_id(text):
    m = re.search(r"\b\d{6,}\b", text)
    return m.group(0) if m else None

def apply_crop(img):
    if st.session_state.crop_box:
        x, y, w, h = st.session_state.crop_box
        return img.crop((x, y, x+w, y+h))
    return img

# =========================
# TABS
# =========================
tab1, tab2 = st.tabs(["🔍 Camera / Search", "📦 Seller Toolkit"])

# =====================================================
# TAB 1 - CAMERA SEARCH
# =====================================================
with tab1:

    cam = st.camera_input("Take Photo")
    upload = st.file_uploader("Upload Image or PDF", type=["png","jpg","jpeg","pdf"])

    file = cam if cam else upload

    if file:

        if upload and upload.type == "application/pdf":
            pages = convert_from_bytes(upload.getvalue(), dpi=200)
        else:
            pages = [Image.open(file).convert("RGB")]

        text_all = ""
        for p in pages:
            fixed = preprocess(p)
            text_all += pytesseract.image_to_string(fixed, config="--psm 6") + "\n\n"

        st.image(pages[0], use_container_width=True)
        st.text_area("Extracted Text", text_all, height=200)
        st.download_button("Download Text", text_all, "text.txt")

# =====================================================
# TAB 2 - SELLER TOOLKIT
# =====================================================
with tab2:

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)

    if pdfs:

        labels = []
        records = []
        seen = set()

        with st.spinner("Processing labels..."):

            for pdf in pdfs:
                pages = convert_from_bytes(pdf.getvalue(), dpi=200)

                for page in pages:
                    fixed = preprocess(page)
                    text = pytesseract.image_to_string(fixed, config="--psm 6")

                    product = detect_product(text)
                    size = detect_size(text)
                    order_id = extract_order_id(text)

                    if order_id and order_id in seen:
                        continue

                    if order_id:
                        seen.add(order_id)

                    labels.append(page)
                    records.append({
                        "product": product,
                        "size": size,
                        "order_id": order_id
                    })

        st.session_state.labels = labels
        st.session_state.df = pd.DataFrame(records)

    # Only continue if labels loaded
    if st.session_state.labels:

        df = st.session_state.df
        labels = st.session_state.labels

        st.subheader("Summary")
        summary = df.groupby(["product","size"]).size().reset_index(name="qty")
        st.dataframe(summary, use_container_width=True)

        # ACTIONS
        st.subheader("Actions")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("✂ Crop"):
                st.session_state.action = "crop"

        with col2:
            if st.button("📄 Merge"):
                st.session_state.action = "merge"

        with col3:
            if st.button("⬇ ZIP All"):
                st.session_state.action = "zip"

        # CROPPING
        if st.session_state.action == "crop":

            st.write("Crop first label (apply to all optional)")
            cropped = st_cropper(labels[0], realtime_update=True)

            w, h = cropped.size
            st.session_state.crop_box = (0, 0, w, h)

            st.session_state.apply_all = st.checkbox("Apply crop to ALL labels", value=True)

            buf = io.BytesIO()
            cropped.save(buf, "PNG")
            st.download_button("Download Cropped Sample", buf.getvalue(), "cropped.png")

        # MERGE
        if st.session_state.action == "merge":

            merged = io.BytesIO()
            imgs = [apply_crop(l) for l in labels]

            imgs[0].save(merged, format="PDF", save_all=True, append_images=imgs[1:])
            st.download_button("Download Merged PDF", merged.getvalue(), "merged.pdf")

        # ZIP
        if st.session_state.action == "zip":

            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w") as z:
                for i, l in enumerate(labels):
                    img = apply_crop(l)
                    b = io.BytesIO()
                    img.save(b, "PNG")
                    z.writestr(f"label_{i+1}.png", b.getvalue())

            st.download_button("Download ZIP", zbuf.getvalue(), "labels.zip")

st.caption("Stable Seller Toolkit • Cloud Safe")
