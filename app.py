import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import io, zipfile, re, hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper
import qrcode

st.set_page_config(page_title="Paper Tools", layout="centered")
st.title("📄 Paper Tools")
st.caption("Search documents • Seller labels • QR generator")

tab1, tab2, tab3 = st.tabs(["🔍 Search Paper", "📦 Seller Labels", "🔗 QR Generator"])

# ---------------- helpers ----------------
def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", str(t).lower())

def highlight(img, data, idx):
    x,y,w,h = data["left"][idx],data["top"][idx],data["width"][idx],data["height"][idx]
    draw = ImageDraw.Draw(img)
    draw.rectangle([x,y,x+w,y+h], outline="red", width=3)
    return img

def apply_crop(img):
    if st.session_state.get("apply_all") and "crop_box" in st.session_state:
        x,y,w,h = st.session_state["crop_box"]
        return img.crop((x,y,x+w,y+h))
    return img

# =====================================================
# TAB 1 — SEARCH PAPER
# =====================================================
with tab1:

    st.session_state.pop("seller_active", None)

    cam = st.camera_input("Take photo")
    upload = st.file_uploader("Upload Image or PDF", type=["png","jpg","jpeg","pdf"])
    query = st.text_input("Search word / number")

    file = cam if cam else upload

    extracted_text = ""

    if file:
        h = hashlib.md5(file.getvalue()).hexdigest()
        if st.session_state.get("hash1") != h:
            st.session_state.clear()
            st.session_state["hash1"] = h

        if "ocr1" not in st.session_state:
            imgs, ocr = [], []

            if upload and upload.type=="application/pdf":
                pages = convert_from_bytes(upload.getvalue(), dpi=200)
            else:
                pages = [Image.open(file).convert("RGB")]

            with st.spinner("Reading document..."):
                for p in pages:
                    gray = p.convert("L")
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                    text = pytesseract.image_to_string(gray)
                    extracted_text += text + "\n\n"
                    imgs.append(p)
                    ocr.append(data)

            st.session_state["imgs1"]=imgs
            st.session_state["ocr1"]=ocr
            st.session_state["text1"]=extracted_text

        st.image(st.session_state["imgs1"][0], use_container_width=True)

        # Show extracted text
        st.text_area("Extracted Text", st.session_state.get("text1",""), height=200)
        st.download_button("⬇ Download Text", st.session_state.get("text1",""), file_name="document.txt")

        if query:
            found=None
            for pi,data in enumerate(st.session_state["ocr1"]):
                for i in range(len(data["text"])):
                    if clean(query) in clean(data["text"][i]):
                        found=(pi,i); break
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

    st.session_state["seller_active"] = True
    st.session_state.pop("imgs1", None)
    st.session_state.pop("ocr1", None)

    st.markdown("### 📦 Seller Labels")

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)
    search_id = st.text_input("Search Order / Tracking")

    if pdfs:
        labels, label_ocr = [], []

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

        if search_id:
            if matches:
                st.success(f"{len(matches)} result(s) found")
                for n,(li,wi) in enumerate(matches):
                    if st.button(f"Open Label {li+1}", key=f"hit{n}"):
                        st.session_state["sel"]=li
                        st.session_state.pop("action",None)
                        img = labels[li].copy()
                        img = highlight(img, label_ocr[li], wi)
                        st.image(img, use_container_width=True)

                        # Download ONLY this label
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        st.download_button("⬇ Download THIS Label", buf.getvalue(), file_name=f"label_{li+1}.png")
            else:
                st.warning("Not found")

        st.subheader("All labels")
        for i,l in enumerate(labels):
            if st.button(f"Select {i+1}", key=f"s{i}"):
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
                if st.button("📄 Merge Selected"):
                    st.session_state["action"]="merge"
            with c3:
                if st.button("⬇ Download All"):
                    st.session_state["action"]="zip"

        if st.session_state.get("action")=="crop":
            cropped=st_cropper(original,realtime_update=True,box_color="#FF0000")
            w,h=cropped.size
            st.session_state["crop_box"]=(0,0,w,h)
            st.session_state["apply_all"]=st.checkbox("Apply crop to ALL labels",value=True)

        if st.session_state.get("action")=="merge":
            selected=[]
            for i in range(len(labels)):
                if st.checkbox(f"Merge {i+1}", key=f"m{i}"):
                    selected.append(i)
            if selected:
                merged=io.BytesIO()
                imgs=[apply_crop(labels[i]) for i in selected]
                imgs[0].save(merged,format="PDF",save_all=True,append_images=imgs[1:])
                st.download_button("📄 Download Merged PDF",merged.getvalue(),file_name="merged_labels.pdf")

        if st.session_state.get("action")=="zip":
            zipbuf=io.BytesIO()
            with zipfile.ZipFile(zipbuf,"w") as z:
                for i,l in enumerate(labels):
                    img=apply_crop(l)
                    b=io.BytesIO()
                    img.save(b,format="PNG")
                    z.writestr(f"label_{i+1}.png",b.getvalue())
            st.download_button("⬇ Download ALL Labels ZIP",zipbuf.getvalue(),file_name="all_labels.zip")

# =====================================================
# TAB 3 — QR GENERATOR
# =====================================================
with tab3:

    st.session_state.pop("imgs1", None)
    st.session_state.pop("ocr1", None)

    st.markdown("### 🔗 QR Code Generator (opens website on scan)")
    url = st.text_input("Enter website / text")

    if url:
        qr = qrcode.make(url)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue())
        st.download_button("⬇ Download QR", buf.getvalue(), file_name="qr.png")

st.markdown("---")
st.caption("Simple tools for paper + ecommerce sellers")
