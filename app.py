import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Lynch & Fisher Terminal Pro",
    layout="wide",
    page_icon="🏛️"
)

# --- CUSTOM CSS THEME ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; }
    .main-header { font-size: 32px; font-weight: 700; color: #0F172A; margin-bottom: 2px; }
    .sub-header { font-size: 16px; color: #64748B; margin-bottom: 20px; }
    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
    }
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1E293B;
        border-left: 4px solid #2563EB;
        padding-left: 10px;
        margin-top: 25px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=1800)
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock, stock.info, stock.history(period="5y")
    except Exception:
        return None, None, None

@st.cache_data(ttl=3600)
def get_peer_data(ticker_list):
    results = []
    for t in ticker_list:
        t = t.strip().upper()
        if not t: continue
        try:
            inf = yf.Ticker(t).info
            results.append({
                "Ticker": t,
                "Name": inf.get("shortName", t),
                "Price": f"${inf.get('currentPrice', 'N/A')}",
                "P/E": round(inf.get("trailingPE", 0), 2) if inf.get("trailingPE") else "N/A",
                "PEG": round(inf.get("pegRatio", 0), 2) if inf.get("pegRatio") else "N/A",
                "Gross Margin (%)": f"{inf.get('grossMargins', 0)*100:.1f}%",
                "Operating Margin (%)": f"{inf.get('operatingMargins', 0)*100:.1f}%",
                "ROE (%)": f"{inf.get('returnOnEquity', 0)*100:.1f}%",
                "D/E Ratio": round(inf.get("debtToEquity", 0)/100, 2) if inf.get("debtToEquity") else "N/A"
            })
        except Exception:
            pass
    return pd.DataFrame(results)

def format_num(num):
    if not num or num == 'N/A': return "N/A"
    if num > 1e12: return f"{num/1e12:.2f}T"
    if num > 1e9: return f"{num/1e9:.2f}B"
    if num > 1e6: return f"{num/1e6:.2f}M"
    return f"{num:,.0f}"

# --- SIDEBAR ---
st.sidebar.markdown("### 🔍 ค้นหา & เฝ้าติดตาม")
ticker_input = st.sidebar.text_input("ชื่อย่อหุ้น (US หรือ หุ้นไทย .BK):", value="NVDA").upper().strip()

# Watchlist System
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["AAPL", "MSFT", "NVDA", "CPALL.BK"]

st.sidebar.markdown("---")
st.sidebar.markdown("#### ⭐ Watchlist ของฉัน")
for w_ticker in st.session_state.watchlist:
    if st.sidebar.button(f"📌 {w_ticker}", key=f"btn_{w_ticker}"):
        ticker_input = w_ticker

add_col1, add_col2 = st.sidebar.columns([3, 1])
new_watch = add_col1.text_input("เพิ่ม Watchlist", placeholder="เช่น TSLA", label_visibility="collapsed")
if add_col2.button("เพิ่ม") and new_watch:
    if new_watch.upper() not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_watch.upper())
        st.rerun()

# --- MAIN DASHBOARD ---
st.markdown('<p class="main-header">🏛️ Lynch & Fisher Investment Terminal</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">ระบบประเมินมูลค่า ตรวจสอบงบการเงิน และวิเคราะห์เชิงคุณภาพ</p>', unsafe_allow_html=True)

if ticker_input:
    with st.spinner(f"กำลังประมวลผลข้อมูล {ticker_input}..."):
        stock_obj, info, hist = get_stock_data(ticker_input)
        income = stock_obj.income_stmt if stock_obj else None
        balance = stock_obj.balance_sheet if stock_obj else None

        if not info or 'shortName' not in info or hist.empty:
            st.error(f"❌ ไม่พบข้อมูลหุ้น '{ticker_input}' กรุณาตรวจสอบชื่อย่ออีกครั้ง")
            st.stop()

        # Overview Header
        c_head1, c_head2, c_head3, c_head4 = st.columns(4)
        c_head1.metric("ราคาตลาด", f"${info.get('currentPrice', 'N/A')}", delta=f"{info.get('regularMarketChangePercent', 0):.2f}%")
        c_head2.metric("Market Cap", format_num(info.get('marketCap', 0)))
        c_head3.metric("Sector / Industry", f"{info.get('sector', 'N/A')}", help=info.get('industry', ''))
        c_head4.metric("Trailing P/E", f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A")

        # Tabs Layout
        tab_lynch, tab_fisher, tab_val, tab_peers, tab_scuttle = st.tabs([
            "📈 Peter Lynch Chart & Rules",
            "🔬 Philip Fisher Quality",
            "🧮 Fair Value & DCF",
            "⚔️ Peer Comparison",
            "🤖 AI Scuttlebutt Assistant"
        ])

        # ==========================================
        # TAB 1: PETER LYNCH CHART & FRAMEWORK
        # ==========================================
        with tab_lynch:
            st.markdown('<p class="section-title">Peter Lynch Earnings Line (ราคาเทียบเส้นกำไร)</p>', unsafe_allow_html=True)
            
            # คำนวณเส้น Peter Lynch Line (Price vs EPS * 15)
            eps_ttm = info.get('trailingEps', None)
            if eps_ttm and len(hist) > 0:
                hist_monthly = hist['Close'].resample('M').last().reset_index()
                lynch_line_val = eps_ttm * 15 # เส้นมาตรฐาน P/E = 15
                
                fig_lynch = go.Figure()
                fig_lynch.add_trace(go.Scatter(x=hist_monthly['Date'], y=hist_monthly['Close'], mode='lines', name='Market Price ($)', line=dict(color='#2563EB', width=2)))
                fig_lynch.add_hline(y=lynch_line_val, line_dash="dash", line_color="#10B981", annotation_text=f"Lynch Fair Value Line (15x EPS = ${lynch_line_val:.2f})", annotation_position="top left")
                
                fig_lynch.update_layout(
                    title=f"กราฟเปรียบเทียบราคาตลาดกับเส้นกำไร 15x P/E ของ Lynch",
                    yaxis_title="ราคา ($)",
                    hovermode="x unified",
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig_lynch, use_container_width=True)
                
                if info.get('currentPrice', 0) < lynch_line_val:
                    st.success(f"💡 **สัญญาณเชิงบวก:** ราคาปัจจุบัน (${info.get('currentPrice')}) อยู่ต่ำกว่าเส้นกำไร 15x (${lynch_line_val:.2f}) ตามทฤษฎีถือว่ามีส่วนลด")
                else:
                    st.info(f"ℹ️ **ข้อสังเกต:** ราคาปัจจุบันสูงกว่าเส้นกำไร 15x (ตลาดให้ Premium บนความคาดหวังการเติบโต)")

            # Lynch Core Metrics Table
            st.markdown('<p class="section-title">Lynch Checklist & Red Flags</p>', unsafe_allow_html=True)
            c_m1, c_m2, c_m3 = st.columns(3)
            
            peg = info.get('pegRatio', None)
            c_m1.metric("PEG Ratio", f"{peg:.2f}" if peg else "N/A", 
                       delta="สมเหตุสมผล (<=1.0)" if peg and peg <= 1.0 else "เริ่มแพง", 
                       delta_color="normal" if peg and peg <= 1.0 else "inverse")
            
            de = info.get('debtToEquity', None)
            c_m2.metric("หนี้สินต่อทุน (D/E)", f"{de/100:.2f}" if de else "N/A",
                       delta="หนี้ต่ำ ปลอดภัย" if de and de < 80 else "หนี้สูง",
                       delta_color="normal" if de and de < 80 else "inverse")
            
            fcf = info.get('freeCashflow', None)
            c_m3.metric("Free Cash Flow", format_num(fcf) if fcf else "N/A")

        # ==========================================
        # TAB 2: PHILIP FISHER QUALITY
        # ==========================================
        with tab_fisher:
            st.markdown('<p class="section-title">1. แนวโน้มอัตรากำไร (Pricing Power & Moat)</p>', unsafe_allow_html=True)
            
            if income is not None and not income.empty and 'Total Revenue' in income.index:
                years = [col.strftime('%Y') for col in income.columns][::-1]
                revs = income.loc['Total Revenue'][::-1]
                
                fig_m = go.Figure()
                if 'Gross Profit' in income.index:
                    gm = (income.loc['Gross Profit'][::-1] / revs) * 100
                    fig_m.add_trace(go.Scatter(x=years, y=gm, mode='lines+markers', name='Gross Margin (%)', line=dict(color='#0284C7', width=3)))
                if 'Operating Income' in income.index:
                    om = (income.loc['Operating Income'][::-1] / revs) * 100
                    fig_m.add_trace(go.Scatter(x=years, y=om, mode='lines+markers', name='Operating Margin (%)', line=dict(color='#D97706', width=3)))
                
                fig_m.update_layout(yaxis_title="Percent (%)", hovermode="x unified", margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig_m, use_container_width=True)

            st.markdown('<p class="section-title">2. เครื่องจักรขับเคลื่อนนวัตกรรม (R&D Intensity)</p>', unsafe_allow_html=True)
            if income is not None and 'Research And Development' in income.index:
                rd = income.loc['Research And Development'][::-1]
                rd_ratio = (rd / revs) * 100
                fig_rd = go.Figure(go.Bar(x=years, y=rd_ratio, marker_color='#0D9488'))
                fig_rd.update_layout(title="สัดส่วนงบวิจัย R&D ต่อยอดขาย (%)", yaxis_title="Percent (%)", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_rd, use_container_width=True)
            else:
                st.info("บริษัทไม่มีการแยกรายงานงบ R&D หรืออยู่ในกลุ่มบริการ")

        # ==========================================
        # TAB 3: FAIR VALUE & DCF CALCULATOR
        # ==========================================
        with tab_val:
            st.markdown('<p class="section-title">เครื่องประเมินมูลค่าหุ้นตามหลัก Peter Lynch & Graham</p>', unsafe_allow_html=True)
            st.caption("ปรับสมมติฐานเพื่อคำนวณราคาที่ควรจะเป็น (Intrinsic Value) และ Margin of Safety:")
            
            c_v1, c_v2 = st.columns(2)
            curr_eps = info.get('trailingEps', 1.0)
            curr_p = info.get('currentPrice', 1.0)
            
            with c_v1:
                growth_rate = st.slider("คาดการณ์อัตราเติบโตกำไรต่อปี (EPS Growth %)", min_value=1.0, max_value=40.0, value=15.0, step=0.5)
                target_pe = st.slider("P/E เหมาะสมที่ควรซื้อ (Target P/E)", min_value=5.0, max_value=50.0, value=20.0, step=1.0)
            
            with c_v2:
                # Lynch Formula: Fair Value = EPS * Growth Rate (or Target P/E)
                fair_value = curr_eps * target_pe
                margin_of_safety = ((fair_value - curr_p) / fair_value) * 100
                
                st.metric("มูลค่าประเมิน (Fair Value)", f"${fair_value:.2f}")
                st.metric("ส่วนเผื่อความปลอดภัย (Margin of Safety)", f"{margin_of_safety:.1f}%",
                          delta="น่าสนใจ (มีส่วนลด)" if margin_of_safety > 0 else "แพงกว่ามูลค่าประเมิน",
                          delta_color="normal" if margin_of_safety > 0 else "inverse")
                
                if margin_of_safety > 20:
                    st.success("🟢 หุ้นอยู่ในโซนราคาถูก มี Margin of Safety มากกว่า 20%")
                elif margin_of_safety > 0:
                    st.warning("🟡 ราคาสมเหตุสมผล แต่ส่วนลดค่อนข้างบาง")
                else:
                    st.error("🔴 ราคาตลาดปัจจุบันสูงกว่ามูลค่าประเมินตามสมมติฐานนี้")

        # ==========================================
        # TAB 4: PEER COMPARISON MATRIX
        # ==========================================
        with tab_peers:
            st.markdown('<p class="section-title">เปรียบเทียบกับคู่แข่งในอุตสาหกรรม (Peer Comparison)</p>', unsafe_allow_html=True)
            
            default_peers = f"{ticker_input}, MSFT, GOOGL, AMZN" if ticker_input not in ["MSFT", "GOOGL", "AMZN"] else "AAPL, MSFT, NVDA"
            peer_input = st.text_input("ใส่รายชื่อหุ้นคู่แข่งที่ต้องการเปรียบเทียบ (คั่นด้วยเครื่องหมายจุลภาค):", value=default_peers)
            
            if peer_input:
                peer_list = [p.strip() for p in peer_input.split(",")]
                df_peers = get_peer_data(peer_list)
                if not df_peers.empty:
                    st.dataframe(df_peers.set_index("Ticker"), use_container_width=True)
                else:
                    st.info("ไม่พบข้อมูลคู่แข่ง")

        # ==========================================
        # TAB 5: AI SCUTTLEBUTT PROMPT GENERATOR
        # ==========================================
        with tab_scuttle:
            st.markdown('<p class="section-title">🤖 AI Scuttlebutt Prompt Generator (สำหรับถาม Gemini / ChatGPT)</p>', unsafe_allow_html=True)
            st.caption("คัดลอกข้อความด้านล่างนี้ไปวางใน AI เพื่อให้ช่วยวิเคราะห์ 15 ข้อเชิงคุณภาพของ Philip Fisher ทันที:")
            
            prompt_text = f"""
คุณเป็นผู้เชี่ยวชาญด้านการลงทุนแนวเน้นคุณค่าสไตล์ Philip Fisher ช่วยวิเคราะห์หุ้น {info.get('longName', ticker_input)} ({ticker_input}) ดังนี้:
1. วิเคราะห์ขีดความสามารถในการแข่งขัน (Economic Moat) และความได้เปรียบทางเทคโนโลยีเหนือคู่แข่ง
2. ประเมินประสิทธิภาพของ R&D และความสามารถในการขยายตลาด (TAM) ในอีก 3-5 ปีข้างหน้า
3. วัฒนธรรมองค์กร ความซื่อสัตย์ และวิสัยทัศน์ของทีมผู้บริหาร
4. ปัจจัยเสี่ยงเชิงคุณภาพ (เช่น การแทรกแซงจากกฎหมาย, การแข่งขันด้านราคา)

ข้อมูลพื้นฐานประกอบ:
- Sector: {info.get('sector', 'N/A')}
- Gross Margin ปัจจุบัน: {info.get('grossMargins', 0)*100:.1f}%
- D/E Ratio: {info.get('debtToEquity', 0)/100:.2f}
โปรดสรุปเป็นข้อๆ อย่างตรงไปตรงมา พร้อมระบุจุดที่ควรระวัง
            """
            st.code(prompt_text, language="text")

