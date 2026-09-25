# Stock Research Terminal

เว็บ Streamlit สำหรับค้นคว้าหุ้นก่อนตัดสินใจลงทุน โดยเน้น **หลักฐานตรวจสอบได้มากกว่าคะแนนหรือสัญญาณซื้อขาย**

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Current architecture

- **SEC EDGAR**: primary-source layer สำหรับ filing history และ XBRL Company Facts
- **Python financial engine**: คำนวณ growth, margins, FCF, debt trend และ metric ที่รองรับจาก SEC facts โดยไม่ให้ AI สร้างตัวเลข
- **yfinance**: ข้อมูลตลาด/ราคาและตัวช่วยเสริมที่ SEC ไม่ได้ให้โดยตรง
- **SQLite**: เก็บ Watchlist, Research Notes และ Evidence สำหรับการใช้งานคนเดียว
- **SEC evidence extraction**: ดึงข้อความสั้น ๆ จาก primary document ของ filing ที่เลือกเพื่อสร้าง candidate evidence ให้ผู้ใช้ตรวจและบันทึกเอง
- **Streamlit**: UI หลัก

SEC ระบุว่า EDGAR APIs มี submissions history และ XBRL financial statement data และ API ของ `data.sec.gov` ไม่ต้องใช้ API key; ข้อมูลถูกอัปเดตใกล้เคียง real time.

## หลักการ

- ไม่สร้าง buy/sell signal
- ไม่ให้ AI คำนวณตัวเลขทางการเงิน
- ไม่เติมค่าที่ไม่มีหลักฐาน: เมื่อข้อมูลไม่พร้อมจะแสดง `N/A`
- Evidence ที่ระบบสกัดจาก filing เป็นเพียง candidate: ผู้ใช้ต้องตรวจต้นฉบับ SEC ก่อนบันทึก
- Evidence แต่ละรายการเก็บ source URL, form, filing date และ period เพื่อย้อนกลับไปยังเอกสารต้นฉบับ
- แยกข้อมูลบริษัทออกจาก scenario ที่ผู้ใช้สมมติ
- ตัวเลขสำคัญควรตรวจสอบกับ annual report / 10-K / 20-F และหมายเหตุประกอบงบ
- Watchlist และ Notes เป็นข้อมูล local ของผู้ใช้คนเดียว และฐานข้อมูล `research.db` จะไม่ถูก commit ตาม `.gitignore`

## SEC User-Agent

สามารถตั้งค่า `SEC_USER_AGENT` ผ่าน Streamlit Secrets หรือ environment variable เพื่อระบุ User-Agent ที่ใช้เรียก SEC

ตัวอย่าง environment variable:

```bash
export SEC_USER_AGENT="Stock Research Terminal/1.0 contact@example.com"
```

อย่าใส่ API key หรือ secret ลงใน source code

## Testing

Regression tests อยู่ที่ `tests/test_financial_engine.py` และ `tests/test_sec_evidence.py`.

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Data source note

SEC เป็นแหล่งหลักสำหรับ financial facts ที่รองรับใน engine ส่วน yfinance ใช้เป็นข้อมูลตลาดและ supplementary data. ความครอบคลุมของ XBRL tags อาจแตกต่างกันตามบริษัทและ taxonomy ดังนั้นระบบจะไม่พยายามเดาค่าที่ไม่มี fact ที่เหมาะสม.
