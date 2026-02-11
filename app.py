import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import cv2
import numpy as np
import io, zipfile, re, hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper
import qrcode

st.set_page_config(page_title="Paper Tools", layout="centered")
st.title("📄 Paper Tools")

tab1, tab2, tab3 = st.tabs(["🔍 Search Paper", "📦 Seller Labels", "🔗 QR Generator"])

def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", str(t).lower())

def preprocess(img):
    npimg = np.array(img)
    gray = cv2.cvtColor(npimg, cv2.COLOR_RGB2GRAY)
    try:
        osd = pytesseract.image_to_osd(gray)
        rot = int(re.search("Rotate: (\d+)", osd).group(1))
        if rot == 90:
            gray = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
        elif rot == 180:
            gray = cv2.rotate(gray, cv2.ROTATE_180)
        elif rot == 270:
            gray = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    except:
        pass
    gray = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,11,2)
    return Image.fromarray(gray)

def highlight(img, data, idx):
    x,y,w,h = data["left"][idx],data["top"][idx],data["width"][idx],data["height"][idx]
    draw = ImageDraw.Draw(img)
    draw.rectangle([x,y,x+w,y+h], outline="red", width=3)
    return img

# ================= TAB 1 =================
with tab1:

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
            text=""

            if upload and upload.type=="application/pdf":
                pages = convert_from_bytes(upload.getvalue(), dpi=200)
            else:
                pages=[Image.open(file).convert("RGB")]

            with st.spinner("Processing..."):
                for p in pages:
                    fixed=preprocess(p)
                    data=pytesseract.image_to_data(fixed,output_type=pytesseract.Output.DICT)
                    txt=pytesseract.image_to_string(fixed)
                    imgs.append(p)
                    ocr.append(data)
                    text+=txt+"\n\n"

            st.session_state["imgs1"]=imgs
            st.session_state["ocr1"]=ocr
            st.session_state["text1"]=text

        st.image(st.session_state["imgs1"][0], use_container_width=True)

        st.text_area("Extracted Text", st.session_state["text1"], height=200)
        st.download_button("⬇ Download Text", st.session_state["text1"], file_name="document.txt")

        if query:
            found=None
            for pi,data in enumerate(st.session_state["ocr1"]):
                for i in range(len(data["text"])):
                    if clean(query) in clean(data["text"][i]):
                        found=(pi,i); break
                if found: break

            if found:
                p,w=found
                img=highlight(st.session_state["imgs1"][p].copy(), st.session_state["ocr1"][p], w)
                st.success("Found")
                st.image(img,use_container_width=True)
            else:
                st.warning("Not found")

# ================= TAB 2 =================
with tab2:

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)
    search = st.text_input("Search Order / Tracking")

    if pdfs:

        labels=[]
        label_ocr=[]

        for pdf in pdfs:
            pages=convert_from_bytes(pdf.getvalue(),dpi=200)
            for p in pages:
                fixed=preprocess(p)
                data=pytesseract.image_to_data(fixed,output_type=pytesseract.Output.DICT)
                labels.append(p)
                label_ocr.append(data)

        st.subheader("All labels")
        for i,l in enumerate(labels):
            st.image(l,width=200)

        if search:

            for li,data in enumerate(label_ocr):
                for i in range(len(data["text"])):
                    if clean(search) in clean(data["text"][i]):

                        img=highlight(labels[li].copy(),label_ocr[li],i)
                        st.image(img,use_container_width=True)

                        buf=io.BytesIO()
                        img.save(buf,"PNG")
                        st.download_button("⬇ Download This Label",buf.getvalue(),file_name=f"label_{li+1}.png")

                        break

# ================= TAB 3 =================
with tab3:

    st.markdown("### Website / Text → QR Code")

    txt = st.text_input("Enter website or text")

    if txt:
        qr=qrcode.make(txt)
        buf=io.BytesIO()
        qr.save(buf,"PNG")
        st.image(buf.getvalue())
        st.download_button("⬇ Download QR", buf.getvalue(), file_name="qr.png")

st.caption("Free OCR + Seller Tools")
