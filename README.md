# Stock Research Terminal

เว็บ Streamlit สำหรับค้นคว้าหุ้นก่อนตัดสินใจลงทุน: ราคา, business overview, growth, financial quality, valuation และ risk checklist

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

หลักการของเวอร์ชันนี้:
- ไม่สร้าง buy/sell signal
- ไม่แต่งตัวเลขทางการเงิน
- แสดง N/A เมื่อข้อมูลไม่พร้อม
- แยก scenario ที่ผู้ใช้สมมติออกจากข้อมูลบริษัท
- ตัวเลขสำคัญควรตรวจสอบกับ annual report/10-K และเอกสารบริษัทก่อนใช้งานจริง

Data: yfinance/Yahoo Finance
