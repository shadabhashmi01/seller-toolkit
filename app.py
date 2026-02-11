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

tab1, tab2 = st.tabs(["📷 Ask Your Paper", "📦 Seller Label Toolkit"])

def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", t.lower())

def apply_crop(img):
    if st.session_state.get("apply_all") and "crop_box" in st.session_state:
        x,y,w,h = st.session_state["crop_box"]
        return img.crop((x,y,x+w,y+h))
    return img

# ================= TAB 1 =================
with tab1:

    st.markdown("### Ask anything from your document")
    st.caption("Examples: total amount • invoice number • student name • due date")

    cam = st.camera_input("📷 Take photo")
    upload = st.file_uploader("Upload Image / PDF", type=["png","jpg","jpeg","pdf"])
    question = st.text_input("Ask your paper")

    # Keep camera image on mobile
    if cam:
        st.session_state["paper_img"] = cam

    file = st.session_state.get("paper_img") if "paper_img" in st.session_state else upload

    if file:

        if "paper_done" not in st.session_state:

            images = []
            words = []

            if upload and upload.type == "application/pdf":
                pages = convert_from_bytes(upload.getvalue(), dpi=200)
            else:
                pages = [Image.open(file).convert("RGB")]

            with st.spinner("Reading document..."):
                for p in pages:
                    gray = p.convert("L")
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                    images.append(p)
                    words.append(data)

            st.session_state["paper_images"] = images
            st.session_state["paper_words"] = words
            st.session_state["paper_done"] = True

    # Simple smart keyword matching
    if question and "paper_words" in st.session_state:

        q = clean(question)
        best = None

        for pi, data in enumerate(st.session_state["paper_words"]):
            for i in range(len(data["text"])):
                t = clean(data["text"][i])
                if q in t or t in q:
                    best = (pi, i)
                    break
            if best:
                break

        if best:

            p, w = best
            img = st.session_state["paper_images"][p].copy()
            d = st.session_state["paper_words"][p]

            x,y,ww,hh = d["left"][w], d["top"][w], d["width"][w], d["height"][w]

            draw = ImageDraw.Draw(img)
            draw.rectangle([x,y,x+ww,y+hh], outline="red", width=3)

            found = d["text"][w]

            st.success(f"Answer: {found}")
            st.image(img, use_container_width=True)

        else:
            st.warning("Couldn't find that. Try simpler words like: amount, name, date.")


# ================= TAB 2 =================
with tab2:

    st.header("📦 Seller Label Toolkit")

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)
    search_id = st.text_input("Search Order / Tracking (optional)")

    if pdfs:

        labels=[]
        label_ocr=[]

        for pdf in pdfs:
            pages=convert_from_bytes(pdf.getvalue(),dpi=200)
            for p in pages:
                gray=p.convert("L")
                data=pytesseract.image_to_data(gray,output_type=pytesseract.Output.DICT)
                labels.append(p.convert("RGB"))
                label_ocr.append(data)

        hits=[]
        s=clean(search_id)

        for idx,data in enumerate(label_ocr):
            for i in range(len(data["text"])):
                if s and s in clean(data["text"][i]):
                    hits.append(idx)

        if search_id:
            for h in set(hits):
                if st.button(f"Label {h+1}"):
                    st.session_state["sel"]=h
                    st.session_state.pop("action",None)

        st.subheader("Click any label")

        for i,l in enumerate(labels):
            if st.button(f"Select {i+1}",key=f"s{i}"):
                st.session_state["sel"]=i
                st.session_state.pop("action",None)
            st.image(l,width=200)

        if "sel" in st.session_state:

            idx=st.session_state["sel"]
            original=labels[idx]

            st.subheader("Choose action")

            c1,c2,c3=st.columns(3)

            with c1:
                if st.button("✂ Crop Label"):
                    st.session_state["action"]="crop"

            with c2:
                if st.button("📄 Merge"):
                    st.session_state["action"]="merge"

            with c3:
                if st.button("⬇ Download"):
                    st.session_state["action"]="download"

        if st.session_state.get("action")=="crop":

            st.subheader("✂ Crop with mouse")

            cropped=st_cropper(original,realtime_update=True,box_color="#FF0000")

            w,h=cropped.size
            st.session_state["crop_box"]=(0,0,w,h)
            st.session_state["apply_all"]=st.checkbox("Apply crop to ALL labels",value=True)

            st.image(cropped,use_container_width=True)

            buf=io.BytesIO()
            cropped.save(buf,format="PNG")
            st.download_button("⬇ Download Cropped PNG",buf.getvalue(),file_name=f"label_{idx+1}.png")

        if st.session_state.get("action")=="merge":

            st.subheader("Select labels to merge")

            selected=[]
            for i in range(len(labels)):
                if st.checkbox(f"Merge {i+1}",key=f"m{i}"):
                    selected.append(i)

            if selected:
                merged=io.BytesIO()
                imgs=[apply_crop(labels[i]) for i in selected]
                imgs[0].save(merged,format="PDF",save_all=True,append_images=imgs[1:])
                st.download_button("📄 Download Merged PDF",merged.getvalue(),file_name="merged_labels.pdf")

        if st.session_state.get("action")=="download":

            zipbuf=io.BytesIO()
            with zipfile.ZipFile(zipbuf,"w") as z:
                for i,l in enumerate(labels):
                    img=apply_crop(l)
                    b=io.BytesIO()
                    img.save(b,format="PNG")
                    z.writestr(f"label_{i+1}.png",b.getvalue())

            st.download_button("⬇ Download ALL Labels ZIP",zipbuf.getvalue(),file_name="all_labels.zip")

st.markdown("---")
st.caption("Built for real-world OCR & ecommerce sellers")

