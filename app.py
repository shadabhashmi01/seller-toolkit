import streamlit as st
import pytesseract
from PIL import Image, ImageDraw
import cv2, numpy as np
import io, re, zipfile, hashlib
from pdf2image import convert_from_bytes
from streamlit_cropper import st_cropper
import pandas as pd

st.set_page_config(page_title="Paper + Seller System", layout="centered")
st.title("📄 Paper + Seller System")

tab1, tab2, tab3 = st.tabs(["🔍 Camera / Search", "📦 Seller Toolkit", "🧠 Smart Product Detection"])

# =========================
# CONFIG
# =========================
PRODUCT_KEYWORDS = {
    "hoodie": ["hoodie"],
    "sweatshirt": ["sweatshirt"],
    "tshirt": ["tshirt", "t-shirt", "tee"],
    "cap": ["cap"],
    "balaclava ninja hoodie": ["balaclava"],
    "sherpa jacket": ["sherpa"],
    "leather jacket": ["leather"],
    "varsity jacket": ["varsity"]
}
SIZES = ["XXXL", "XXL", "XL", "L", "M", "S"]

# =========================
# HELPERS
# =========================
def clean(t):
    return re.sub(r"[^a-zA-Z0-9]", "", str(t).lower())

def preprocess(img):
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5,5), 0)
    gray = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,11,2)
    return Image.fromarray(gray)

def highlight(img, data, i):
    x,y,w,h=data["left"][i],data["top"][i],data["width"][i],data["height"][i]
    draw=ImageDraw.Draw(img)
    draw.rectangle([x,y,x+w,y+h],outline="red",width=3)
    return img, (x,y,w,h)

def detect_product(text):
    t=text.lower()
    for p,keys in PRODUCT_KEYWORDS.items():
        for k in keys:
            if k in t: return p
    return "Unknown"

def detect_size(text):
    t=text.upper()
    for s in SIZES:
        if re.search(rf"\b{s}\b", t): return s
    return "Unknown"

def extract_order_id(text):
    m=re.search(r"\b\d{6,}\b", text)
    return m.group(0) if m else None

def apply_crop(img):
    if st.session_state.get("apply_all") and "crop_box" in st.session_state:
        x,y,w,h=st.session_state["crop_box"]
        return img.crop((x,y,x+w,y+h))
    return img

# =====================================================
# TAB 1 — CAMERA / SEARCH
# =====================================================
with tab1:
    cam = st.camera_input("Take Photo")
    upload = st.file_uploader("Upload Image or PDF", type=["png","jpg","jpeg","pdf"])
    query = st.text_input("Search text")

    file = cam if cam else upload

    if file:
        h=hashlib.md5(file.getvalue()).hexdigest()
        if st.session_state.get("hash1")!=h:
            st.session_state.clear()
            st.session_state["hash1"]=h

        if "ocr1" not in st.session_state:
            imgs=[]; ocr=[]; full=""
            if upload and upload.type=="application/pdf":
                pages=convert_from_bytes(upload.getvalue(),dpi=200)
            else:
                pages=[Image.open(file).convert("RGB")]
            with st.spinner("Extracting..."):
                for p in pages:
                    fixed=preprocess(p)
                    data=pytesseract.image_to_data(fixed,output_type=pytesseract.Output.DICT)
                    txt=pytesseract.image_to_string(fixed,config="--psm 6")
                    imgs.append(p); ocr.append(data); full+=txt+"\n\n"
            st.session_state["imgs1"]=imgs
            st.session_state["ocr1"]=ocr
            st.session_state["text1"]=full

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
                img,box=highlight(st.session_state["imgs1"][found[0]].copy(),
                                  st.session_state["ocr1"][found[0]],found[1])
                st.image(img,use_container_width=True)
                # download only found area
                x,y,w,h=box
                crop=st.session_state["imgs1"][found[0]].crop((x,y,x+w,y+h))
                buf=io.BytesIO(); crop.save(buf,"PNG")
                st.download_button("⬇ Download Found Area",buf.getvalue(),"found.png")
            else:
                st.warning("Not found")

# =====================================================
# TAB 2 — SELLER TOOLKIT
# =====================================================
with tab2:

    st.subheader("📤 Upload Label PDFs")
    pdfs = st.file_uploader("Select PDFs", type=["pdf"], accept_multiple_files=True)

    @st.cache_data(show_spinner=False)
    def load_labels(files):
        labels=[]
        records=[]
        seen=set()

        for pdf in files:
            pages=convert_from_bytes(pdf.getvalue(),dpi=200)

            for page in pages:
                fixed=preprocess(page)
                text=pytesseract.image_to_string(fixed,config="--psm 6")

                product=detect_product(text)
                size=detect_size(text)
                oid=extract_order_id(text)

                if oid and oid in seen:
                    continue
                if oid:
                    seen.add(oid)

                labels.append(page)
                records.append({
                    "product":product,
                    "size":size,
                    "order_id":oid
                })

        return labels, pd.DataFrame(records)

    if pdfs:

        with st.spinner("Reading labels (cached)…"):
            labels, df = load_labels(pdfs)

        # SUMMARY
        st.subheader("📊 Summary")
        summary=df.groupby(["product","size"]).size().reset_index(name="qty")
        st.dataframe(summary,use_container_width=True)

        # SEARCH
        st.subheader("🔎 Search Order ID")
        search=st.text_input("Enter Order / Tracking")

        if search:
            for i,row in df.iterrows():
                if row["order_id"] and clean(search) in clean(row["order_id"]):
                    st.image(labels[i],use_container_width=True)
                    b=io.BytesIO(); labels[i].save(b,"PNG")
                    st.download_button("⬇ Download This Label",b.getvalue(),f"label_{i+1}.png")
                    break

        # ACTION PANEL
        st.subheader("🧰 Actions")

        c1,c2,c3=st.columns(3)
        with c1:
            if st.button("✂ Crop"):
                st.session_state["action"]="crop"
        with c2:
            if st.button("📄 Merge"):
                st.session_state["action"]="merge"
        with c3:
            if st.button("⬇ ZIP All"):
                st.session_state["action"]="zip"

        # CROPPING
        if st.session_state.get("action")=="crop":
            st.subheader("Crop First Label (apply to all optional)")
            cropped=st_cropper(labels[0],realtime_update=True)
            w,h=cropped.size
            st.session_state["crop_box"]=(0,0,w,h)
            st.session_state["apply_all"]=st.checkbox("Apply crop to ALL labels",value=True)

            buf=io.BytesIO(); cropped.save(buf,"PNG")
            st.download_button("⬇ Download Cropped Sample",buf.getvalue(),"cropped.png")

        # MERGE
        if st.session_state.get("action")=="merge":
            merged=io.BytesIO()
            imgs=[apply_crop(l) for l in labels]
            imgs[0].save(merged,format="PDF",save_all=True,append_images=imgs[1:])
            st.download_button("⬇ Download Merged PDF",merged.getvalue(),"merged.pdf")

        # ZIP
        if st.session_state.get("action")=="zip":
            zbuf=io.BytesIO()
            with zipfile.ZipFile(zbuf,"w") as z:
                for i,l in enumerate(labels):
                    img=apply_crop(l); b=io.BytesIO(); img.save(b,"PNG")
                    z.writestr(f"label_{i+1}.png",b.getvalue())
            st.download_button("⬇ Download ZIP",zbuf.getvalue(),"labels.zip")

        # GROUPED PDF
        st.subheader("📦 Grouped PDFs")

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

        st.download_button("⬇ Download Grouped PDFs ZIP",gbuf.getvalue(),"grouped_labels.zip")

        # PACKING EXCEL
        xbuf=io.BytesIO()
        summary.to_excel(xbuf,index=False)
        st.download_button("⬇ Download Packing Excel",xbuf.getvalue(),"packing.xlsx")

# =====================================================
# TAB 3 — SMART PRODUCT DETECTION (SINGLE IMAGE)
# =====================================================
with tab3:
    cam = st.camera_input("Take Label Photo")
    upload = st.file_uploader("Upload Label Image", type=["png","jpg","jpeg"])
    file = cam if cam else upload
    if file:
        img=Image.open(file).convert("RGB")
        fixed=preprocess(img)
        text=pytesseract.image_to_string(fixed,config="--psm 6")
        st.image(img,use_container_width=True)
        st.subheader("Detected")
        st.write("Product:", detect_product(text))
        st.write("Size:", detect_size(text))
        st.write("Order ID:", extract_order_id(text))

