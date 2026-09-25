import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from financial_engine import build_sec_financial_quality
from storage import add_watchlist, init_db, list_notes, save_note, remove_watchlist

st.set_page_config(page_title="Stock Research Terminal", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Sarabun',sans-serif}
.block-container{max-width:1500px;padding-top:1.5rem}
.section{font-size:1.15rem;font-weight:700;margin:18px 0 10px}
.note{padding:12px 14px;border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0}
</style>
""", unsafe_allow_html=True)

def fmt_money(x):
    if x is None or pd.isna(x): return "N/A"
    x=float(x); a=abs(x)
    if a>=1e12: return "$%.2fT"%(x/1e12)
    if a>=1e9: return "$%.2fB"%(x/1e9)
    if a>=1e6: return "$%.2fM"%(x/1e6)
    return "$%,.0f"%x

def fmt_pct(x):
    if x is None or pd.isna(x): return "N/A"
    return "%.1f%%"%(float(x)*100)

def fmt_num(x):
    if x is None or pd.isna(x): return "N/A"
    return "%,.2f"%float(x)

def safe_ratio(a,b):
    if a is None or b is None or pd.isna(a) or pd.isna(b) or b==0: return None
    return a/b

def latest_row(df,names):
    if df is None or df.empty: return None
    for n in names:
        if n in df.index:
            s=pd.to_numeric(df.loc[n],errors="coerce").dropna()
            if len(s): return float(s.iloc[0])
    return None

def cagr(df,names,periods=3):
    if df is None or df.empty: return None
    for n in names:
        if n in df.index:
            s=pd.to_numeric(df.loc[n],errors="coerce").dropna()
            if len(s)>=periods+1:
                old,new=float(s.iloc[periods]),float(s.iloc[0])
                if old>0 and new>0: return (new/old)**(1/periods)-1
    return None

@st.cache_data(ttl=900,show_spinner=False)
def load_stock(ticker):
    s=yf.Ticker(ticker)
    return s.info or {},s.history(period="5y",auto_adjust=False),s.income_stmt,s.balance_sheet,s.cashflow

# --- SEC PRIMARY SOURCE LAYER ---
import requests
import pandas as pd
import streamlit as st

SEC_USER_AGENT = st.secrets.get("SEC_USER_AGENT", os.getenv("SEC_USER_AGENT", "Stock Research Terminal/1.0"))
SEC_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

@st.cache_data(ttl=3600, show_spinner=False)
def sec_ticker_map():
    r=requests.get("https://www.sec.gov/files/company_tickers.json",headers=SEC_HEADERS,timeout=20)
    r.raise_for_status()
    data=r.json()
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}

@st.cache_data(ttl=3600, show_spinner=False)
def sec_submissions(cik):
    r=requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",headers=SEC_HEADERS,timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600, show_spinner=False)
def sec_companyfacts(cik):
    r=requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",headers=SEC_HEADERS,timeout=30)
    r.raise_for_status()
    return r.json()

def sec_filing_rows(ticker):
    cik=sec_ticker_map().get(ticker)
    if not cik: return pd.DataFrame(), None
    sub=sec_submissions(cik)
    recent=sub.get("filings",{}).get("recent",{})
    rows=[]
    for i,form in enumerate(recent.get("form",[])):
        if form in ("10-K","10-Q","20-F","6-K"):
            rows.append({
                "Form":form,
                "Filed":recent["filingDate"][i],
                "Period":recent["reportDate"][i],
                "Accession":recent["accessionNumber"][i],
                "Document":recent["primaryDocument"][i],
                "URL":f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{recent['accessionNumber'][i].replace('-','')}/{recent['primaryDocument'][i]}"
            })
        if len(rows)>=12: break
    return pd.DataFrame(rows), cik

def sec_fact_series(facts, tags):
    for taxonomy,tag in tags:
        units=facts.get("facts",{}).get(taxonomy,{}).get(tag,{}).get("units",{})
        if not units: continue
        unit=next(iter(units))
        rows=units[unit]
        annual=[x for x in rows if x.get("fp")=="FY" and x.get("form") in ("10-K","20-F")]
        annual=sorted(annual,key=lambda x:x.get("filed",""),reverse=True)
        if annual:
            return pd.DataFrame(annual)
    return pd.DataFrame()

def sec_financial_snapshot(ticker):
    try:
        _,cik=sec_filing_rows(ticker)
        if not cik: return {}
        facts=sec_companyfacts(cik)
        out={}
        tag_map={
            "Revenue":[("us-gaap","RevenueFromContractWithCustomerExcludingAssessedTax"),("us-gaap","Revenues")],
            "Gross Profit":[("us-gaap","GrossProfit")],
            "Operating Income":[("us-gaap","OperatingIncomeLoss")],
            "Net Income":[("us-gaap","NetIncomeLoss")],
            "Operating Cash Flow":[("us-gaap","NetCashProvidedByUsedInOperatingActivities")],
            "Capital Expenditure":[("us-gaap","PaymentsToAcquirePropertyPlantAndEquipment")],
            "Assets":[("us-gaap","Assets")],
            "Liabilities":[("us-gaap","Liabilities")],
            "Cash":[("us-gaap","CashAndCashEquivalentsAtCarryingValue")],
            "Debt Current":[("us-gaap","LongTermDebtCurrent")],
            "Debt Noncurrent":[("us-gaap","LongTermDebtNoncurrent")],
            "Diluted Shares":[("us-gaap","WeightedAverageNumberOfDilutedSharesOutstanding")]
        }
        for label,tags in tag_map.items():
            df=sec_fact_series(facts,tags)
            if not df.empty:
                out[label]=df
        return out
    except Exception as e:
        return {"_error":str(e)}

def sec_addon(ticker):
    st.markdown("### 🏛️ SEC EDGAR — Primary-source layer")
    st.caption("SEC EDGAR submissions และ XBRL company facts เป็นข้อมูลจากเอกสารที่ยื่นต่อ SEC; API ของ SEC ไม่ต้องใช้ API key และมีข้อมูล filings/XBRL แบบอัปเดตต่อเนื่อง. citeturn0search0")
    filings,cik=sec_filing_rows(ticker)
    if filings.empty:
        st.info("ไม่พบ SEC filing mapping สำหรับ ticker นี้")
        return
    st.write("CIK:",cik)
    display=filings[["Form","Filed","Period","URL"]].copy()
    st.dataframe(display,hide_index=True,use_container_width=True,column_config={"URL":st.column_config.LinkColumn("SEC Filing")})
    snap=sec_financial_snapshot(ticker)
    if snap.get("_error"):
        st.warning("SEC XBRL โหลดไม่สำเร็จ: "+snap["_error"])
        return
    st.markdown("#### SEC financial facts")
    records=[]
    for label,df in snap.items():
        if isinstance(df,pd.DataFrame) and not df.empty:
            x=df.iloc[0]
            records.append({"Fact":label,"Value":x.get("val"),"Unit":x.get("uom",""),"Filed":x.get("filed"),"FY":x.get("fy"),"Form":x.get("form"),"Accession":x.get("accn","")})
    if records: st.dataframe(pd.DataFrame(records),hide_index=True,use_container_width=True)

init_db()
if "watchlist" not in st.session_state:
    saved = list_watchlist()
    if not saved:
        for seed in ["NVDA","MSFT","AAPL","GOOGL"]:
            add_watchlist(seed)
        saved = list_watchlist()
    st.session_state.watchlist = saved

st.sidebar.title("📊 Stock Research")
ticker=st.sidebar.text_input("Ticker",value="NVDA",placeholder="AAPL, NVDA, MSFT").strip().upper()
st.sidebar.markdown("### ⭐ Watchlist")
for item in st.session_state.watchlist:
    if st.sidebar.button(item,use_container_width=True,key="watch_"+item): ticker=item
new_ticker=st.sidebar.text_input("เพิ่มหุ้น",placeholder="เช่น AMZN")
if st.sidebar.button("เพิ่มเข้า Watchlist",use_container_width=True) and new_ticker.strip():
    t=new_ticker.strip().upper()
    if t not in st.session_state.watchlist:
        add_watchlist(t)
        st.session_state.watchlist = list_watchlist()
        st.rerun()
remove_ticker = st.sidebar.selectbox("ลบออกจาก Watchlist", ["—"] + st.session_state.watchlist)
if remove_ticker != "—" and st.sidebar.button("ลบหุ้น", use_container_width=True):
    remove_watchlist(remove_ticker)
    st.session_state.watchlist = list_watchlist()
    st.rerun()
st.sidebar.divider()
st.sidebar.caption("ข้อมูลมาจาก yfinance และ SEC EDGAR; ความครอบคลุมอาจต่างกันตามบริษัท")
st.sidebar.caption("SEC User-Agent: ตั้งค่า SEC_USER_AGENT ใน Secrets/Environment")
st.sidebar.caption("อัปเดตหน้า: "+datetime.now().strftime("%Y-%m-%d %H:%M"))

if not ticker: st.info("ใส่ ticker เพื่อเริ่มค้นคว้าหุ้น"); st.stop()
try:
    with st.spinner("กำลังโหลดข้อมูล "+ticker+"..."): info,hist,income,balance,cashflow=load_stock(ticker)
except Exception as e:
    st.error("โหลดข้อมูลไม่สำเร็จ: "+str(e)); st.stop()

price=info.get("currentPrice") or info.get("regularMarketPrice")
if not info or price is None:
    st.error("ไม่พบข้อมูลที่เพียงพอสำหรับ "+ticker); st.stop()
name=info.get("longName") or info.get("shortName") or ticker
change=info.get("regularMarketChangePercent")

st.title(name+" ("+ticker+")")
st.caption("Research before investing — รวบรวมข้อมูลให้ตรวจสอบเอง ไม่ใช่ระบบแนะนำซื้อหรือขาย")

c1,c2,c3,c4,c5=st.columns(5)
c1.metric("ราคาล่าสุด","$%.2f"%price,"%.2f%%"%change if change is not None else None)
c2.metric("Market Cap",fmt_money(info.get("marketCap")))
c3.metric("Trailing P/E",fmt_num(info.get("trailingPE")))
c4.metric("Forward P/E",fmt_num(info.get("forwardPE")))
c5.metric("Dividend Yield",fmt_pct(info.get("dividendYield")))
st.caption("Sector: "+str(info.get("sector","N/A"))+" · Industry: "+str(info.get("industry","N/A")))

tab1,tab2,tab3,tab4,tab5=st.tabs(["📌 Overview","📈 Growth & Quality","💰 Valuation","⚠️ Risks & Checklist","🏛️ SEC Evidence"])

with tab1:
    st.markdown('<div class="section">ราคาย้อนหลัง 5 ปี</div>',unsafe_allow_html=True)
    if hist is not None and not hist.empty:
        fig=go.Figure(go.Scatter(x=hist.index,y=hist["Close"],mode="lines",name="Close"))
        fig.update_layout(height=420,margin=dict(l=0,r=0,t=20,b=0),hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True)
    else: st.info("ไม่มี historical price data")
    st.markdown('<div class="section">บริษัททำอะไร?</div>',unsafe_allow_html=True)
    st.write(info.get("longBusinessSummary","ไม่มี business description"))
    st.markdown('<div class="section">ข้อมูลพื้นฐาน</div>',unsafe_allow_html=True)
    base=pd.DataFrame({"รายการ":["Employees","Country","Exchange","52W High","52W Low","Beta","Shares Outstanding"],
    "ข้อมูล":[info.get("fullTimeEmployees","N/A"),info.get("country","N/A"),info.get("exchange","N/A"),
    "$%.2f"%info["fiftyTwoWeekHigh"] if info.get("fiftyTwoWeekHigh") else "N/A",
    "$%.2f"%info["fiftyTwoWeekLow"] if info.get("fiftyTwoWeekLow") else "N/A",
    fmt_num(info.get("beta")), "%,.0f"%info["sharesOutstanding"] if info.get("sharesOutstanding") else "N/A"]})
    st.dataframe(base,hide_index=True,use_container_width=True)

with tab2:
    sec_quality = {}
    try:
        sec_snapshot = sec_financial_snapshot(ticker)
        if sec_snapshot and not sec_snapshot.get("_error"):
            sec_quality = build_sec_financial_quality(sec_snapshot)
    except Exception:
        sec_quality = {}

    sec_latest = sec_quality.get("latest", {})
    if sec_latest:
        st.markdown('<div class="section">SEC Financial Quality — deterministic calculations</div>',unsafe_allow_html=True)
        st.caption("คำนวณด้วย Python จาก annual SEC XBRL facts โดยตรง ไม่ใช้ AI คำนวณตัวเลข")
        sy = sec_latest.get("fiscal_year")
        a,b,c,d = st.columns(4)
        a.metric("Revenue CAGR (3Y)",fmt_pct(sec_latest.get("revenue_cagr_3y")))
        b.metric("Net Income CAGR (3Y)",fmt_pct(sec_latest.get("net_income_cagr_3y")))
        c.metric("FCF Margin",fmt_pct(sec_latest.get("fcf_margin")))
        d.metric("Operating Margin",fmt_pct(sec_latest.get("operating_margin")))
        st.caption(f"SEC fiscal year: {sy} · Source: SEC EDGAR Company Facts")

        series = sec_quality.get("series", {})
        sec_rows = [
            {"Metric":"Revenue","Value":fmt_money(sec_latest.get("revenue"))},
            {"Metric":"Net Income","Value":fmt_money(sec_latest.get("net_income"))},
            {"Metric":"Operating Cash Flow","Value":fmt_money(series.get("Operating Cash Flow",{}).get(sy)) if sy else "N/A"},
            {"Metric":"Capital Expenditure","Value":fmt_money(series.get("Capital Expenditure",{}).get(sy)) if sy else "N/A"},
            {"Metric":"Free Cash Flow","Value":fmt_money(series.get("Free Cash Flow",{}).get(sy)) if sy else "N/A"},
            {"Metric":"Cash","Value":fmt_money(sec_latest.get("cash"))},
            {"Metric":"Debt","Value":fmt_money(sec_latest.get("debt"))},
            {"Metric":"Net Debt","Value":fmt_money(sec_latest.get("net_debt"))},
            {"Metric":"ROA (simple)","Value":fmt_pct(sec_latest.get("roa_simple"))},
            {"Metric":"Debt YoY","Value":fmt_pct(sec_latest.get("debt_change_yoy"))},
            {"Metric":"Diluted Shares YoY","Value":fmt_pct(sec_latest.get("diluted_shares_yoy"))},
        ]
        st.dataframe(pd.DataFrame(sec_rows),hide_index=True,use_container_width=True)

        trend_df = pd.DataFrame(sec_quality.get("trend",[]))
        if not trend_df.empty:
            st.markdown('<div class="section">SEC annual trend</div>',unsafe_allow_html=True)
            st.dataframe(trend_df,hide_index=True,use_container_width=True)
    else:
        st.info("SEC Financial Quality ยังไม่มีข้อมูลเพียงพอสำหรับ ticker นี้; metrics จาก yfinance ด้านล่างเป็นข้อมูลเสริม")

    revenue=latest_row(income,["Total Revenue"]); gross=latest_row(income,["Gross Profit"])
    op=latest_row(income,["Operating Income"]); net=latest_row(income,["Net Income"])
    rd=latest_row(income,["Research And Development"])
    rg=cagr(income,["Total Revenue"]); gm=safe_ratio(gross,revenue); om=safe_ratio(op,revenue)
    nm=safe_ratio(net,revenue); rdi=safe_ratio(rd,revenue)
    st.markdown('<div class="section">Growth & profitability</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric("Revenue CAGR* (3Y)",fmt_pct(rg)); b.metric("Earnings Growth",fmt_pct(info.get("earningsGrowth")))
    c.metric("Gross Margin",fmt_pct(gm)); d.metric("Operating Margin",fmt_pct(om))
    st.caption("*คำนวณจาก annual statements ที่ yfinance ส่งกลับมา")
    de=info.get("debtToEquity")
    q=pd.DataFrame({"Metric":["Free Cash Flow","ROE","ROA","Debt / Equity","Current Ratio","Net Margin","R&D / Revenue"],
    "Value":[fmt_money(info.get("freeCashflow")),fmt_pct(info.get("returnOnEquity")),fmt_pct(info.get("returnOnAssets")),
    fmt_num(de/100 if de is not None else None),fmt_num(info.get("currentRatio")),fmt_pct(nm),fmt_pct(rdi)]})
    st.markdown('<div class="section">Financial quality</div>',unsafe_allow_html=True)
    st.dataframe(q,hide_index=True,use_container_width=True)
    st.markdown('<div class="section">Revenue / earnings trend</div>',unsafe_allow_html=True)
    if income is not None and not income.empty:
        rows={}
        for label,candidates in {"Revenue":["Total Revenue"],"Operating Income":["Operating Income"],"Net Income":["Net Income"]}.items():
            for n in candidates:
                if n in income.index:
                    rows[label]=pd.to_numeric(income.loc[n],errors="coerce").dropna().sort_index(); break
        if rows:
            df=pd.DataFrame(rows); fig=go.Figure()
            for col in df.columns: fig.add_trace(go.Bar(x=[str(x.year) for x in df.index],y=df[col],name=col))
            fig.update_layout(barmode="group",height=380,margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig,use_container_width=True)
    else: st.info("ไม่มี annual income statement")

with tab3:
    st.markdown('<div class="section">Valuation snapshot</div>',unsafe_allow_html=True)
    vals=pd.DataFrame({"Metric":["Current Price","Trailing P/E","Forward P/E","PEG","Price / Sales","Price / Book","EV / EBITDA"],
    "Value":["$%.2f"%price,fmt_num(info.get("trailingPE")),fmt_num(info.get("forwardPE")),fmt_num(info.get("pegRatio")),
    fmt_num(info.get("priceToSalesTrailing12Months")),fmt_num(info.get("priceToBook")),fmt_num(info.get("enterpriseToEbitda"))]})
    st.dataframe(vals,hide_index=True,use_container_width=True)
    st.markdown('<div class="section">Scenario calculator — ไม่ใช่คำแนะนำราคา</div>',unsafe_allow_html=True)
    st.caption("ใช้ดู sensitivity ของสมมติฐานเท่านั้น")
    eps=info.get("trailingEps")
    if eps and eps>0:
        x,y,z=st.columns(3)
        target_pe=x.number_input("สมมติฐาน P/E",1.0,100.0,20.0,1.0)
        growth=y.number_input("EPS growth ต่อปี (%)",-50.0,100.0,15.0,1.0)
        years=z.number_input("จำนวนปี",1,10,5,1)
        future_eps=eps*((1+growth/100)**years); scenario=future_eps*target_pe
        st.metric("Scenario EPS × P/E","$%.2f"%scenario)
        st.caption("เริ่มจาก trailing EPS $%.2f"%eps)
    else: st.info("ไม่มี trailing EPS ที่เหมาะสำหรับ scenario นี้")
    div=pd.DataFrame({"รายการ":["Dividend Rate","Dividend Yield","Payout Ratio","5Y Avg Dividend Yield"],
    "ข้อมูล":[fmt_money(info.get("dividendRate")),fmt_pct(info.get("dividendYield")),fmt_pct(info.get("payoutRatio")),fmt_pct(info.get("fiveYearAvgDividendYield"))]})
    st.markdown('<div class="section">Dividend</div>',unsafe_allow_html=True); st.dataframe(div,hide_index=True,use_container_width=True)

with tab4:
    st.markdown('<div class="section">Risk checklist</div>',unsafe_allow_html=True)
    de=info.get("debtToEquity"); fcf=info.get("freeCashflow")
    risks=pd.DataFrame({"หัวข้อ":["Revenue/customer concentration","Debt & interest burden","Stock-based compensation / dilution","Cash flow vs earnings","Margin trend","Competition","Regulatory / legal exposure","Management capital allocation","Valuation expectations"],
    "สิ่งที่ระบบมี":["ต้องอ่าน annual report / 10-K เพิ่ม","D/E: "+fmt_num(de/100 if de is not None else None),"ต้องตรวจ diluted shares และงบ","FCF: "+fmt_money(fcf),"Operating margin: "+fmt_pct(safe_ratio(latest_row(income,["Operating Income"]),latest_row(income,["Total Revenue"]))),"ต้องอ่านคู่แข่งเพิ่มเติม","ต้องตรวจ filings","ต้องอ่าน shareholder letter / filings","Forward P/E: "+fmt_num(info.get("forwardPE"))]})
    st.dataframe(risks,hide_index=True,use_container_width=True)
    st.markdown('<div class="section">ก่อนตัดสินใจควรตรวจอะไร?</div>',unsafe_allow_html=True)
    st.markdown("""<div class="note"><b>1.</b> Annual report / 10-K และหมายเหตุประกอบงบ<br><b>2.</b> รายงานไตรมาสล่าสุดและคำอธิบายของผู้บริหาร<br><b>3.</b> Revenue drivers, customers, competitors และ market structure<br><b>4.</b> Cash flow, debt, dilution และ stock-based compensation<br><b>5.</b> Valuation เทียบกับ growth ที่ตลาดกำลังคาดหวัง</div>""",unsafe_allow_html=True)

    st.markdown('<div class="section">Research Notes</div>',unsafe_allow_html=True)
    note = st.text_area("บันทึกสำหรับหุ้นนี้",placeholder="สมมติฐาน คำถามจาก 10-K หรือสิ่งที่ต้องตรวจต่อ...",key="research_note")
    if st.button("บันทึก Note",key="save_note") :
        if note.strip():
            save_note(ticker,note)
            st.success("บันทึกแล้ว")
        else:
            st.warning("ใส่ข้อความก่อนบันทึก")
    saved_notes = list_notes(ticker)
    if saved_notes:
        notes_df = pd.DataFrame(saved_notes)
        notes_df["created_at"] = pd.to_datetime(notes_df["created_at"],errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
        notes_df = notes_df.rename(columns={"created_at":"Created","note":"Note"}).drop(columns=["id"])
        st.dataframe(notes_df,hide_index=True,use_container_width=True)

with tab5:
    sec_addon(ticker)
    st.caption("SEC layer ใช้ submissions history และ XBRL Company Facts จาก SEC เป็นหลัก; ตัวเลขจะแสดง filing form และวันที่ยื่นเพื่อช่วยตรวจสอบย้อนกลับ.")

st.divider()
st.caption("Stock Research Terminal · ใช้เพื่อการศึกษาและการค้นคว้าด้วยตนเอง · ไม่มี buy/sell signal")
