import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import io
import zipfile
import re
import hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper

st.set_page_config(page_title="Document Search & Seller Toolkit", layout="centered")

st.title("📄 Document Search + 📦 Seller Toolkit")
st.caption("Camera OCR • PDF search • Amazon / Flipkart label tools")

tab1, tab2 = st.tabs(["📷 Camera & Document Search", "📦 Seller Label Toolkit"])

def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", t.lower())

def apply_crop(img):
    if st.session_state.get("apply_all") and "crop_box" in st.session_state:
        x, y, w, h = st.session_state["crop_box"]
        return img.crop((x, y, x+w, y+h))
    return img

# ================= TAB 1 =================
with tab1:

    st.info("📱 Mobile tip: Camera scanning works great on phone. For large PDFs and seller tools, desktop/laptop gives best performance.")

    colA, colB = st.columns(2)

    with colA:
        if st.button("🔄 New Document"):
            st.session_state.clear()
            st.rerun()

    with colB:
        if st.button("🧹 Clear Document"):
            st.session_state.pop("mobile_img", None)
            st.session_state.pop("images", None)
            st.session_state.pop("ocr", None)
            st.session_state.pop("text", None)
            st.session_state.pop("selected", None)
            st.rerun()

    cam = st.camera_input("📷 Take photo")
    upload = st.file_uploader("Upload Image / PDF", type=["png","jpg","jpeg","pdf"])
    query = st.text_input("Search text")

    if cam:
        st.session_state["mobile_img"] = cam

    file = st.session_state.get("mobile_img") if "mobile_img" in st.session_state else upload

    if file:
        h = hashlib.md5(file.getvalue()).hexdigest()
    else:
        h = None

    if h and st.session_state.get("doc_hash") != h:
        st.session_state.clear()
        st.session_state["doc_hash"] = h

    if file and "ocr_done" not in st.session_state:

        images = []
        ocr = []
        full_text = ""

        if upload and upload.type == "application/pdf":
            pages = convert_from_bytes(upload.getvalue(), dpi=200)
        else:
            pages = [Image.open(file).convert("RGB")]

        for p in pages:
            gray = p.convert("L")
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            txt = pytesseract.image_to_string(gray)
            images.append(p)
            ocr.append(data)
            full_text += txt + "\n\n"

        st.session_state["images"] = images
        st.session_state["ocr"] = ocr
        st.session_state["text"] = full_text
        st.session_state["ocr_done"] = True

    matches = []

    if "images" in st.session_state:

        if "selected" not in st.session_state:
            st.image(st.session_state["images"][0], use_container_width=True)

        for pidx, data in enumerate(st.session_state["ocr"]):
            for i in range(len(data["text"])):
                if query and clean(query) in clean(data["text"][i]):
                    matches.append((pidx, i))

        if query:
            if matches:
                for i, (p, w) in enumerate(matches):
                    if st.button(f"{i+1}. {st.session_state['ocr'][p]['text'][w]} (Page {p+1})"):
                        st.session_state["selected"] = (p, w)
            else:
                st.warning("No match")

    if "selected" in st.session_state:
        p, w = st.session_state["selected"]
        img = st.session_state["images"][p].copy()
        d = st.session_state["ocr"][p]
        x, y, ww, hh = d["left"][w], d["top"][w], d["width"][w], d["height"][w]
        draw = ImageDraw.Draw(img)
        draw.rectangle([x, y, x+ww, y+hh], outline="red", width=3)
        st.image(img, use_container_width=True)

    if "text" in st.session_state:
        st.text_area("Extracted Text", st.session_state["text"], height=200)
        st.download_button("⬇ Download Text", st.session_state["text"], file_name="text.txt")

# ================= TAB 2 =================
with tab2:

    st.header("📦 Seller Label Toolkit")
    st.caption("Upload → Search → Crop once → Apply to all → Download")

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)
    search_id = st.text_input("Search Order / Tracking (optional)")

    if pdfs:

        labels = []
        label_ocr = []

        for pdf in pdfs:
            pages = convert_from_bytes(pdf.getvalue(), dpi=200)
            for p in pages:
                gray = p.convert("L")
                data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                labels.append(p.convert("RGB"))
                label_ocr.append(data)

        hits = []
        s = clean(search_id)

        for idx, data in enumerate(label_ocr):
            for i in range(len(data["text"])):
                if s and s in clean(data["text"][i]):
                    hits.append(idx)

        if search_id:
            for h in set(hits):
                if st.button(f"Label {h+1}"):
                    st.session_state["sel"] = h

        st.subheader("Click any label")

        for i, l in enumerate(labels):
            if st.button(f"Select {i+1}", key=f"s{i}"):
                st.session_state["sel"] = i
            st.image(l, width=200)

        if "sel" in st.session_state:

            idx = st.session_state["sel"]
            original = labels[idx]

            st.subheader("✂ Crop with mouse")

            cropped = st_cropper(original, realtime_update=True, box_color="#FF0000")

            w, h = cropped.size
            st.session_state["crop_box"] = (0, 0, w, h)
            st.session_state["apply_all"] = st.checkbox("Apply crop to ALL labels", value=True)

            st.image(cropped, use_container_width=True)

            c1, c2 = st.columns(2)

            buf = io.BytesIO()
            cropped.save(buf, format="PNG")
            with c1:
                st.download_button("⬇ PNG", buf.getvalue(), file_name=f"label_{idx+1}.png")

            buf2 = io.BytesIO()
            cropped.save(buf2, format="PDF")
            with c2:
                st.download_button("⬇ PDF", buf2.getvalue(), file_name=f"label_{idx+1}.pdf")

        st.subheader("Merge Labels")

        selected = []
        for i in range(len(labels)):
            if st.checkbox(f"Merge {i+1}", key=f"m{i}"):
                selected.append(i)

        if selected:
            merged = io.BytesIO()
            imgs = [apply_crop(labels[i]) for i in selected]
            imgs[0].save(merged, format="PDF", save_all=True, append_images=imgs[1:])
            st.download_button("📄 Download Merged PDF", merged.getvalue(), file_name="merged_labels.pdf")

        zipbuf = io.BytesIO()
        with zipfile.ZipFile(zipbuf, "w") as z:
            for i, l in enumerate(labels):
                img = apply_crop(l)
                b = io.BytesIO()
                img.save(b, format="PNG")
                z.writestr(f"label_{i+1}.png", b.getvalue())

        st.download_button("⬇ Download ALL Labels ZIP", zipbuf.getvalue(), file_name="all_labels.zip")

st.markdown("---")
st.caption("Built for real-world OCR & ecommerce sellers")
