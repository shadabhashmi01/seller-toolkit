import streamlit as st
import pytesseract
from PIL import Image
import cv2, numpy as np
import io, re, zipfile
from pdf2image import convert_from_bytes
import pandas as pd

st.set_page_config(page_title="Smart Paper & Seller Toolkit", layout="centered")
st.title("📄 Smart Paper & Seller Toolkit")

# ---------------- SESSION ----------------

if "labels" not in st.session_state:
    st.session_state.labels=[]
if "df" not in st.session_state:
    st.session_state.df=None
if "crop_box" not in st.session_state:
    st.session_state.crop_box=None

# ---------------- CONFIG ----------------

PRODUCT_KEYWORDS={
"hoodie":["hoodie"],
"sweatshirt":["sweatshirt"],
"tshirt":["tshirt","t-shirt"],
"cap":["cap"],
"balaclava ninja hoodie":["balaclava"],
"sherpa jacket":["sherpa"],
"leather jacket":["leather"],
"varsity jacket":["varsity"]
}

SIZES=["XXXL","XXL","XL","L","M","S"]

# ---------------- HELPERS ----------------

def clean(t):
    return re.sub(r"[^a-zA-Z0-9]","",str(t).lower())

def preprocess(img):
    arr=np.array(img)
    gray=cv2.cvtColor(arr,cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(gray,(5,5),0)
    gray=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,11,2)
    return gray

def detect_product(t):
    t=t.lower()
    for p,k in PRODUCT_KEYWORDS.items():
        for x in k:
            if x in t: return p
    return "Unknown"

def detect_size(t):
    t=t.upper()
    for s in SIZES:
        if re.search(rf"\b{s}\b",t): return s
    return "Unknown"

def extract_order_id(t):
    m=re.search(r"\b\d{6,}\b",t)
    return m.group(0) if m else None

def apply_crop(img):
    if st.session_state.crop_box:
        x,y,w,h=st.session_state.crop_box
        return img.crop((x,y,x+w,y+h))
    return img

# ================= TABS =================

tab1,tab2,tab3=st.tabs(["🔍 Scan & Search","📦 Seller Toolkit","🧠 Quick Label Check"])

# =====================================================
# TAB 1 — SCAN & SEARCH
# =====================================================

with tab1:

    cam=st.camera_input("Take Photo")
    upload=st.file_uploader("Upload Image or PDF",type=["png","jpg","jpeg","pdf"])
    query=st.text_input("Search word / number")

    file=cam if cam else upload

    if file:

        if upload and upload.type=="application/pdf":
            pages=convert_from_bytes(upload.getvalue(),dpi=200)
        else:
            pages=[Image.open(file).convert("RGB")]

        full=""
        ocr=[]

        for p in pages:
            fixed=preprocess(p)
            data=pytesseract.image_to_data(fixed,output_type=pytesseract.Output.DICT)
            text=pytesseract.image_to_string(fixed,config="--psm 6")
            ocr.append(data)
            full+=text+"\n\n"

        st.image(pages[0],use_container_width=True)
        st.text_area("Extracted Text",full,height=200)
        st.download_button("⬇ Download Text",full,"text.txt")

        if query:
            found=False
            for pi,data in enumerate(ocr):
                for i in range(len(data["text"])):
                    if clean(query) in clean(data["text"][i]):
                        crop=pages[pi].crop((
                            data["left"][i],
                            data["top"][i],
                            data["left"][i]+data["width"][i],
                            data["top"][i]+data["height"][i]
                        ))
                        st.image(crop,use_container_width=True)
                        b=io.BytesIO(); crop.save(b,"PNG")
                        st.download_button("⬇ Download Found Area",b.getvalue(),"found.png")
                        found=True
                        break
                if found: break
            if not found:
                st.warning("Not found")

# =====================================================
# TAB 2 — SELLER TOOLKIT
# =====================================================

with tab2:

    pdfs=st.file_uploader("Upload Label PDFs",type=["pdf"],accept_multiple_files=True)

    if pdfs:

        labels=[]
        records=[]
        seen=set()

        for pdf in pdfs:
            pages=convert_from_bytes(pdf.getvalue(),dpi=200)
            for page in pages:
                fixed=preprocess(page)
                text=pytesseract.image_to_string(fixed,config="--psm 6")

                prod=detect_product(text)
                size=detect_size(text)
                oid=extract_order_id(text)

                if oid and oid in seen: continue
                if oid: seen.add(oid)

                labels.append(page)
                records.append({"product":prod,"size":size,"order":oid})

        st.session_state.labels=labels
        st.session_state.df=pd.DataFrame(records)

    if st.session_state.labels:

        labels=st.session_state.labels
        df=st.session_state.df

        st.subheader("Summary")
        summary=df.groupby(["product","size"]).size().reset_index(name="qty")
        st.dataframe(summary,use_container_width=True)

        st.subheader("Crop (pixels)")
        st.image(labels[0],use_container_width=True)

        c1,c2,c3,c4=st.columns(4)
        x=c1.number_input("X",0,5000,0)
        y=c2.number_input("Y",0,5000,0)
        w=c3.number_input("Width",0,5000,400)
        h=c4.number_input("Height",0,5000,400)

        if st.button("Apply Crop To All"):
            st.session_state.crop_box=(x,y,w,h)

        colA,colB=st.columns(2)

        with colA:
            if st.button("Merge All"):
                buf=io.BytesIO()
                imgs=[apply_crop(i) for i in labels]
                imgs[0].save(buf,format="PDF",save_all=True,append_images=imgs[1:])
                st.download_button("⬇ Download Merged PDF",buf.getvalue(),"merged.pdf")

        with colB:
            if st.button("ZIP All"):
                zbuf=io.BytesIO()
                with zipfile.ZipFile(zbuf,"w") as z:
                    for i,l in enumerate(labels):
                        img=apply_crop(l)
                        b=io.BytesIO(); img.save(b,"PNG")
                        z.writestr(f"label_{i+1}.png",b.getvalue())
                st.download_button("⬇ Download ZIP",zbuf.getvalue(),"labels.zip")

        grouped={}
        for i,row in df.iterrows():
            key=f"{row['product']} - {row['size']}"
            grouped.setdefault(key,[]).append(labels[i])

        gbuf=io.BytesIO()
        with zipfile.ZipFile(gbuf,"w") as z:
            for k,imgs in grouped.items():
                pbuf=io.BytesIO()
                imgs[0].save(pbuf,format="PDF",save_all=True,append_images=imgs[1:])
                z.writestr(f"{k}.pdf",pbuf.getvalue())

        st.download_button("⬇ Download Grouped PDFs",gbuf.getvalue(),"grouped_labels.zip")

        excel=io.BytesIO()
        summary.to_excel(excel,index=False)
        st.download_button("⬇ Download Packing Excel",excel.getvalue(),"packing.xlsx")

# =====================================================
# TAB 3 — QUICK LABEL CHECK
# =====================================================

with tab3:

    cam=st.camera_input("Take Label Photo")
    upload=st.file_uploader("Upload Label Image",type=["png","jpg","jpeg"])
    file=cam if cam else upload

    if file:
        img=Image.open(file).convert("RGB")
        fixed=preprocess(img)
        text=pytesseract.image_to_string(fixed,config="--psm 6")

        st.image(img,use_container_width=True)
        st.write("Product:",detect_product(text))
        st.write("Size:",detect_size(text))
        st.write("Order ID:",extract_order_id(text))

st.caption("Offline • Mobile Friendly • Seller Ready")
