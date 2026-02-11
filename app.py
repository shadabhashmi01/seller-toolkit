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

    st.markdown("### 📷 Ask Your Paper")
    st.caption("Upload or take photo • Ask something like: total amount, invoice number, student name")

    cam = st.camera_input("Take Photo")
    upload = st.file_uploader("Upload Image or PDF", type=["png","jpg","jpeg","pdf"])
    question = st.text_input("Ask your paper")

    # Determine active file (latest input wins)
    file = cam if cam else upload

    if file:

        # Unique file hash to detect change
        file_hash = hashlib.md5(file.getvalue()).hexdigest()

        if st.session_state.get("current_hash") != file_hash:
            st.session_state.clear()
            st.session_state["current_hash"] = file_hash

        if "ocr_ready" not in st.session_state:

            images = []
            ocr_data = []

            if upload and upload.type == "application/pdf":
                pages = convert_from_bytes(upload.getvalue(), dpi=200)
            else:
                pages = [Image.open(file).convert("RGB")]

            with st.spinner("Reading document..."):
                for page in pages:
                    gray = page.convert("L")
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                    images.append(page)
                    ocr_data.append(data)

            st.session_state["images"] = images
            st.session_state["ocr_data"] = ocr_data
            st.session_state["ocr_ready"] = True

        # Show first page by default
        st.image(st.session_state["images"][0], use_container_width=True)

        # Smart Ask Logic
        if question and "ocr_data" in st.session_state:

            q = clean(question)
            best_match = None

            # Basic keyword expansion
            keyword_map = {
                "amount": ["total", "amount", "rs", "₹", "balance"],
                "date": ["date", "issued", "due"],
                "name": ["name", "student", "customer"],
                "invoice": ["invoice", "bill", "no"]
            }

            expanded_words = [q]

            for key, values in keyword_map.items():
                if key in q:
                    expanded_words.extend(values)

            for page_index, data in enumerate(st.session_state["ocr_data"]):
                for i in range(len(data["text"])):
                    word = clean(data["text"][i])
                    if any(k in word for k in expanded_words):
                        best_match = (page_index, i)
                        break
                if best_match:
                    break

            if best_match:

                p, w = best_match
                img = st.session_state["images"][p].copy()
                data = st.session_state["ocr_data"][p]

                x = data["left"][w]
                y = data["top"][w]
                w_box = data["width"][w]
                h_box = data["height"][w]

                draw = ImageDraw.Draw(img)
                draw.rectangle([x, y, x+w_box, y+h_box], outline="red", width=3)

                found_word = data["text"][w]

                st.success(f"Answer found: {found_word}")
                st.image(img, use_container_width=True)

            else:
                st.warning("Could not find a matching answer. Try simpler keywords like amount, date, name.")
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



