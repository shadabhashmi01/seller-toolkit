import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import io
import zipfile
import re
import hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper
import barcode
from barcode.writer import ImageWriter

st.set_page_config(page_title="Paper Tools", layout="centered")

st.title("📄 Paper Tools")
st.caption("Search documents • Seller labels • Barcode generator")

tab1, tab2, tab3 = st.tabs(["🔍 Search Paper", "📦 Seller Labels", "🏷 Text → Barcode"])

# ---------------- helpers ----------------

def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", str(t).lower())

def highlight(img, data, idx):
    x,y,w,h = data["left"][idx],data["top"][idx],data["width"][idx],data["height"][idx]
    draw = ImageDraw.Draw(img)
    draw.rectangle([x,y,x+w,y+h], outline="red", width=3)
    return img

# =====================================================
# TAB 1 — SEARCH PAPER (Camera / Image / PDF)
# =====================================================
with tab1:

    st.markdown("### 🔍 Search Paper")

    cam = st.camera_input("Take photo")
    upload = st.file_uploader("Upload Image or PDF", type=["png","jpg","jpeg","pdf"])
    query = st.text_input("Search word / number")

    file = cam if cam else upload

    if file:

        h = hashlib.md5(file.getvalue()).hexdigest()

        if st.session_state.get("hash1") != h:
            st.session_state.clear()
            st.session_state["hash1"] = h

        if "ocr1" not in st.session_state:

            imgs=[]
            ocr=[]

            if upload and upload.type=="application/pdf":
                pages = convert_from_bytes(upload.getvalue(), dpi=200)
            else:
                pages = [Image.open(file).convert("RGB")]

            with st.spinner("Reading document..."):
                for p in pages:
                    gray = p.convert("L")
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                    imgs.append(p)
                    ocr.append(data)

            st.session_state["imgs1"]=imgs
            st.session_state["ocr1"]=ocr

        st.image(st.session_state["imgs1"][0], use_container_width=True)

        if query:

            found=None

            for pi,data in enumerate(st.session_state["ocr1"]):
                for i in range(len(data["text"])):
                    if clean(query) in clean(data["text"][i]):
                        found=(pi,i)
                        break
                if found: break

            if found:
                p,w = found
                img = st.session_state["imgs1"][p].copy()
                img = highlight(img, st.session_state["ocr1"][p], w)
                st.success(f"Found: {st.session_state['ocr1'][p]['text'][w]}")
                st.image(img, use_container_width=True)
            else:
                st.warning("Not found")

# =====================================================
# TAB 2 — SELLER LABELS
# =====================================================
with tab2:

    # stop camera session when entering seller tab
    st.session_state.pop("imgs1",None)
    st.session_state.pop("ocr1",None)

    st.markdown("### 📦 Seller Labels")

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)
    search_id = st.text_input("Search Order / Tracking")

    if pdfs:

        labels=[]
        label_ocr=[]

        for pdf in pdfs:
            pages = convert_from_bytes(pdf.getvalue(), dpi=200)
            for p in pages:
                gray=p.convert("L")
                data=pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                labels.append(p.convert("RGB"))
                label_ocr.append(data)

        matches=[]

        if search_id:
            for li,data in enumerate(label_ocr):
                for i in range(len(data["text"])):
                    if clean(search_id) in clean(data["text"][i]):
                        matches.append((li,i))

        if matches:
            st.success(f"{len(matches)} result(s) found")

            for n,(li,wi) in enumerate(matches):
                if st.button(f"Open Label {li+1}", key=f"hit{n}"):

                    img = labels[li].copy()
                    img = highlight(img, label_ocr[li], wi)
                    st.image(img, use_container_width=True)

        elif search_id:
            st.warning("Not found")

        st.subheader("All labels")

        for i,l in enumerate(labels):
            st.image(l,width=200)

# =====================================================
# TAB 3 — TEXT TO BARCODE
# =====================================================
with tab3:

    st.markdown("### 🏷 Convert Text to Barcode")

    txt = st.text_input("Enter any text / tracking number")

    if txt:

        CODE128 = barcode.get_barcode_class('code128')
        code = CODE128(txt, writer=ImageWriter())

        buffer = io.BytesIO()
        code.write(buffer)

        st.image(buffer.getvalue())

        st.download_button(
            "⬇ Download Barcode",
            buffer.getvalue(),
            file_name="barcode.png"
        )

st.markdown("---")
st.caption("Simple tools for paper + sellers")
