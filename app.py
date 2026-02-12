import streamlit as st
import pytesseract
from PIL import Image
import cv2, numpy as np
import io, re, zipfile
from pdf2image import convert_from_bytes
import pandas as pd

st.set_page_config(page_title="Seller Toolkit", layout="centered")
st.title("📦 Seller Toolkit (Cloud Stable)")

# ================= SESSION =================

if "labels" not in st.session_state:
    st.session_state.labels=[]

if "df" not in st.session_state:
    st.session_state.df=None

if "crop_box" not in st.session_state:
    st.session_state.crop_box=None

if "action" not in st.session_state:
    st.session_state.action=None

# ================= CONFIG =================

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

# ================= HELPERS =================

def preprocess(img):
    arr=np.array(img)
    gray=cv2.cvtColor(arr,cv2.COLOR_RGB2GRAY)
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

# ================= UI =================

pdfs=st.file_uploader("Upload Label PDFs",type=["pdf"],accept_multiple_files=True)

if pdfs:

    labels=[]
    records=[]
    seen=set()

    with st.spinner("Processing PDFs..."):

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

# ================= AFTER LOAD =================

if st.session_state.labels:

    labels=st.session_state.labels
    df=st.session_state.df

    st.subheader("Summary")
    summary=df.groupby(["product","size"]).size().reset_index(name="qty")
    st.dataframe(summary,use_container_width=True)

    st.subheader("First Label Preview")
    st.image(labels[0],use_container_width=True)

    st.subheader("Crop Box (pixels)")

    col1,col2,col3,col4=st.columns(4)
    x=col1.number_input("X",0,5000,0)
    y=col2.number_input("Y",0,5000,0)
    w=col3.number_input("Width",0,5000,400)
    h=col4.number_input("Height",0,5000,400)

    if st.button("Apply Crop To All"):
        st.session_state.crop_box=(x,y,w,h)

    colA,colB=st.columns(2)

    with colA:
        if st.button("📄 Merge PDF"):
            st.session_state.action="merge"

    with colB:
        if st.button("⬇ ZIP All"):
            st.session_state.action="zip"

    # MERGE
    if st.session_state.action=="merge":
        buf=io.BytesIO()
        imgs=[apply_crop(i) for i in labels]
        imgs[0].save(buf,format="PDF",save_all=True,append_images=imgs[1:])
        st.download_button("Download Merged PDF",buf.getvalue(),"merged.pdf")

    # ZIP
    if st.session_state.action=="zip":
        zbuf=io.BytesIO()
        with zipfile.ZipFile(zbuf,"w") as z:
            for i,l in enumerate(labels):
                img=apply_crop(l)
                b=io.BytesIO()
                img.save(b,"PNG")
                z.writestr(f"label_{i+1}.png",b.getvalue())
        st.download_button("Download ZIP",zbuf.getvalue(),"labels.zip")

    # PACKING EXCEL
    excel=io.BytesIO()
    summary.to_excel(excel,index=False)
    st.download_button("Download Packing Excel",excel.getvalue(),"packing.xlsx")

st.caption("Cloud Safe Seller Toolkit • No crashes")
