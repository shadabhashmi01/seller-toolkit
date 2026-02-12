import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import cv2, numpy as np
import io, zipfile, re, hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper

st.set_page_config(page_title="Paper + Seller Tools", layout="centered")
st.title("📄 Paper + Seller Tools")

tab1, tab2 = st.tabs(["🔍 Search Paper", "📦 Seller Toolkit"])

# ---------- helpers ----------

def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", str(t).lower())

def preprocess(img):
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

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

    gray = cv2.GaussianBlur(gray,(5,5),0)
    gray = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,11,2)

    return Image.fromarray(gray)

def highlight(img,data,i):
    x,y,w,h=data["left"][i],data["top"][i],data["width"][i],data["height"][i]
    draw=ImageDraw.Draw(img)
    draw.rectangle([x,y,x+w,y+h],outline="red",width=3)
    return img

def apply_crop(img):
    if st.session_state.get("apply_all") and "crop_box" in st.session_state:
        x,y,w,h=st.session_state["crop_box"]
        return img.crop((x,y,x+w,y+h))
    return img

# ================= TAB 1 =================
with tab1:

    cam = st.camera_input("Take photo")
    upload = st.file_uploader("Upload Image or PDF", type=["png","jpg","jpeg","pdf"])
    query = st.text_input("Search text")

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
                pages=convert_from_bytes(upload.getvalue(),dpi=200)
            else:
                pages=[Image.open(file).convert("RGB")]

            with st.spinner("Reading document..."):
                for p in pages:
                    fixed=preprocess(p)
                    data=pytesseract.image_to_data(fixed,output_type=pytesseract.Output.DICT)
                    txt=pytesseract.image_to_string(fixed,config="--psm 6")
                    imgs.append(p)
                    ocr.append(data)
                    text+=txt+"\n\n"

            st.session_state["imgs1"]=imgs
            st.session_state["ocr1"]=ocr
            st.session_state["text1"]=text

        st.image(st.session_state["imgs1"][0],use_container_width=True)

        st.text_area("Extracted Text",st.session_state["text1"],height=200)
        st.download_button("⬇ Download Text",st.session_state["text1"],file_name="text.txt")

        if query:
            found=None
            for pi,data in enumerate(st.session_state["ocr1"]):
                for i in range(len(data["text"])):
                    if clean(query) in clean(data["text"][i]):
                        found=(pi,i);break
                if found:break

            if found:
                p,w=found
                img=highlight(st.session_state["imgs1"][p].copy(),st.session_state["ocr1"][p],w)
                st.image(img,use_container_width=True)
            else:
                st.warning("Not found")

# ================= TAB 2 =================
with tab2:

    pdfs = st.file_uploader("Upload Label PDFs", type=["pdf"], accept_multiple_files=True)
    search = st.text_input("Search order / tracking")

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

        st.subheader("All Labels")
        for i,l in enumerate(labels):
            if st.button(f"Select {i+1}",key=f"s{i}"):
                st.session_state["sel"]=i
                st.session_state.pop("action",None)
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

        if "sel" in st.session_state:

            original=labels[st.session_state["sel"]]

            c1,c2,c3=st.columns(3)
            with c1:
                if st.button("✂ Crop"):
                    st.session_state["action"]="crop"
            with c2:
                if st.button("📄 Merge"):
                    st.session_state["action"]="merge"
            with c3:
                if st.button("⬇ ZIP"):
                    st.session_state["action"]="zip"

        if st.session_state.get("action")=="crop":
            cropped=st_cropper(original,realtime_update=True)
            w,h=cropped.size
            st.session_state["crop_box"]=(0,0,w,h)
            st.session_state["apply_all"]=st.checkbox("Apply crop to all",value=True)

        if st.session_state.get("action")=="merge":
            selected=[]
            for i in range(len(labels)):
                if st.checkbox(f"Merge {i+1}",key=f"m{i}"):
                    selected.append(i)
            if selected:
                merged=io.BytesIO()
                imgs=[apply_crop(labels[i]) for i in selected]
                imgs[0].save(merged,format="PDF",save_all=True,append_images=imgs[1:])
                st.download_button("Download merged PDF",merged.getvalue(),"merged.pdf")

        if st.session_state.get("action")=="zip":
            zipbuf=io.BytesIO()
            with zipfile.ZipFile(zipbuf,"w") as z:
                for i,l in enumerate(labels):
                    img=apply_crop(l)
                    b=io.BytesIO()
                    img.save(b,"PNG")
                    z.writestr(f"label_{i+1}.png",b.getvalue())
            st.download_button("Download all labels ZIP",zipbuf.getvalue(),"labels.zip")

st.caption("Stable OCR + Seller Toolkit")
