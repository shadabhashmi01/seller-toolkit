import streamlit as st
import pytesseract
import cv2
import numpy as np
from PIL import Image
import io
import zipfile
import re
import hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper

# ================= CONFIG =================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\Library\bin"

st.set_page_config(page_title="Search Docs & Seller Toolkit", layout="centered")

st.title("📄 Document Search & 📦 Seller Toolkit")
st.caption("Search printed documents • Prepare Flipkart/Amazon labels")

tab1, tab2 = st.tabs(["📷 Camera & Document Search", "📦 Seller Label Toolkit"])

# ================= HELPERS =================
def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", t.lower())

def apply_crop(img):
    if st.session_state.get("apply_all") and "crop_box" in st.session_state:
        x, y, w, h = st.session_state["crop_box"]
        return img[y:y+h, x:x+w]
    return img

# =====================================================
# TAB 1 — CAMERA / IMAGE / PDF SEARCH
# =====================================================
with tab1:

    if st.button("🔄 New Document"):
        st.session_state.clear()
        st.rerun()

    cam = st.camera_input("📷 Take photo of document")
    upload = st.file_uploader("Upload Image / PDF", type=["png","jpg","jpeg","pdf"])
    query = st.text_input("Search text")

    file = cam if cam else upload

    if file:
        h = hashlib.md5(file.getvalue()).hexdigest()
    else:
        h = None

    if h and st.session_state.get("doc_hash") != h:
        st.session_state.clear()
        st.session_state["doc_hash"] = h

    if file and "ocr_done" not in st.session_state:

        images, ocr_data, full_text = [], [], ""

        if upload and upload.type == "application/pdf":
            pages = convert_from_bytes(upload.getvalue(), dpi=200, poppler_path=POPPLER_PATH)
        else:
            pages = [Image.open(file).convert("RGB")]

        for p in pages:
            img = np.array(p)
            bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            txt = pytesseract.image_to_string(gray)

            images.append(bgr)
            ocr_data.append(data)
            full_text += txt + "\n\n"

        st.session_state["images"] = images
        st.session_state["ocr"] = ocr_data
        st.session_state["text"] = full_text
        st.session_state["ocr_done"] = True

    matches = []

    if "images" in st.session_state:

        if "selected" not in st.session_state:
            st.image(cv2.cvtColor(st.session_state["images"][0], cv2.COLOR_BGR2RGB),
                     use_container_width=True)

        for pidx, data in enumerate(st.session_state["ocr"]):
            for i in range(len(data["text"])):
                if query and clean(query) in clean(data["text"][i]):
                    matches.append((pidx, i))

        if query:
            if matches:
                st.subheader("Results")
                for i, (p, w) in enumerate(matches):
                    if st.button(f"{i+1}. {st.session_state['ocr'][p]['text'][w]} (Page {p+1})"):
                        st.session_state["selected"] = (p, w)
            else:
                st.warning("No match found")

    if "selected" in st.session_state:
        p, w = st.session_state["selected"]
        img = st.session_state["images"][p].copy()
        d = st.session_state["ocr"][p]
        x, y, ww, hh = d["left"][w], d["top"][w], d["width"][w], d["height"][w]
        cv2.rectangle(img, (x,y), (x+ww, y+hh), (255,0,0), 3)
        st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), use_container_width=True)

    if "text" in st.session_state:
        st.text_area("Extracted Text", st.session_state["text"], height=200)
        st.download_button("⬇ Download Text", st.session_state["text"], file_name="text.txt")

# =====================================================
# TAB 2 — SELLER LABEL TOOLKIT
# =====================================================
with tab2:

    st.header("📦 Seller Label Toolkit")
    st.caption("Upload → Search → Crop once → Apply to all → Download")

    pdfs = st.file_uploader(
        "Upload Shipping Label PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    search_id = st.text_input("Search Order / Tracking ID (optional)")

    if pdfs:

        all_images, all_ocr = [], []

        for pdf in pdfs:
            pages = convert_from_bytes(pdf.getvalue(), dpi=200, poppler_path=POPPLER_PATH)
            for p in pages:
                img = np.array(p)
                bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                all_images.append(bgr)
                all_ocr.append(data)

        # SEARCH LABELS
        hits = []
        s = clean(search_id)

        for idx, data in enumerate(all_ocr):
            for i in range(len(data["text"])):
                if s and s in clean(data["text"][i]):
                    hits.append(idx)

        if search_id:
            st.subheader("Found Labels")
            for h in set(hits):
                if st.button(f"Label {h+1}"):
                    st.session_state["sel"] = h

        st.subheader("Click any label to crop")

        for i, img in enumerate(all_images):
            if st.button(f"Select Label {i+1}", key=f"lbl{i}"):
                st.session_state["sel"] = i
            st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), width=200)

        # MOUSE CROP
        if "sel" in st.session_state:

            idx = st.session_state["sel"]
            original = Image.fromarray(cv2.cvtColor(all_images[idx], cv2.COLOR_BGR2RGB))

            st.subheader("✂ Crop with mouse")

            cropped = st_cropper(
                original,
                realtime_update=True,
                box_color="#FF0000"
            )

            np_crop = np.array(cropped)
            h, w, _ = np_crop.shape
            st.session_state["crop_box"] = (0, 0, w, h)
            st.session_state["apply_all"] = st.checkbox(
                "Apply this crop to ALL labels (Flipkart recommended)",
                value=True
            )

            st.image(np_crop, use_container_width=True)

            c1, c2 = st.columns(2)

            buf = io.BytesIO()
            cropped.save(buf, format="PNG")
            with c1:
                st.download_button("⬇ Download PNG", buf.getvalue(),
                                   file_name=f"label_{idx+1}.png")

            buf2 = io.BytesIO()
            cropped.save(buf2, format="PDF")
            with c2:
                st.download_button("⬇ Download PDF", buf2.getvalue(),
                                   file_name=f"label_{idx+1}.pdf")

        # MERGE
        st.subheader("Merge Selected Labels")

        selected = []
        for i in range(len(all_images)):
            if st.checkbox(f"Merge Label {i+1}", key=f"m{i}"):
                selected.append(i)

        if selected:
            merged = io.BytesIO()
            imgs = []
            for i in selected:
                img = apply_crop(all_images[i])
                imgs.append(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))

            imgs[0].save(merged, format="PDF", save_all=True, append_images=imgs[1:])
            st.download_button("📄 Download Merged PDF", merged.getvalue(),
                               file_name="merged_labels.pdf")

        # ZIP
        zipbuf = io.BytesIO()
        with zipfile.ZipFile(zipbuf, "w") as z:
            for i, img in enumerate(all_images):
                final = apply_crop(img)
                buf = io.BytesIO()
                Image.fromarray(cv2.cvtColor(final, cv2.COLOR_BGR2RGB)).save(buf, format="PNG")
                z.writestr(f"label_{i+1}.png", buf.getvalue())

        st.download_button("⬇ Download ALL Labels (ZIP)",
                           zipbuf.getvalue(),
                           file_name="all_labels.zip")

st.markdown("---")
st.caption("Built for real-world use • Camera + Search + Seller tools")
