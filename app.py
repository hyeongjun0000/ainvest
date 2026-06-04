import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date
import warnings

warnings.filterwarnings("ignore")

# ── 1. Data Manager Class ──────────────────────────────────────────────────
class MarketDataManager:
    """시장 데이터를 가져오고 파싱하는 역할을 담당하는 클래스"""
    
    @staticmethod
    def detect_market(ticker):
        """한국 주식 여부 판단"""
        upper = ticker.upper()
        if upper.endswith(".KS"):
            return True, "KOSPI", "₩", "🇰🇷"
        elif upper.endswith(".KQ"):
            return True, "KOSDAQ", "₩", "🇰🇷"
        else:
            return False, "NASDAQ/NYSE", "$", "🇺🇸"

    @staticmethod
    @st.cache_data(ttl=300)
    def get_hist(ticker, period, interval):
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df.dropna(subset=["Close"])

    @staticmethod
    @st.cache_data(ttl=600)
    def get_fx():
        try:
            return float(yf.Ticker("USDKRW=X").fast_info["lastPrice"])
        except:
            return 1380.0


# ── 2. Analyzer Class ──────────────────────────────────────────────────────
class StockAnalyzer:
    """주식의 보조지표 계산, AI 전략 및 리스크 스코어를 산출하는 클래스"""
    
    SIGNAL_META = {
        "strong_short": ("⚡ STRONG SHORT", "#8b00ff", "인버스 ETF 매수 · 풋옵션 고려"),
        "short":        ("🔻 SHORT",        "#4a9eff", "인버스 ETF 분할 매수 고려"),
        "hodl":         ("⏸ HODL",          "#888888", "현금 보유 또는 소량 포지션 유지"),
        "long":         ("🔺 LONG",         "#ff9500", "분할 매수 진입 고려"),
        "strong_long":  ("🚀 STRONG LONG",  "#e84040", "콜옵션 · 적극 매수 진입 고려"),
    }

    @staticmethod
    def calc_stoch(df, k=14, d=3):
        lo  = df["Low"].rolling(k).min()
        hi  = df["High"].rolling(k).max()
        pk  = 100 * (df["Close"] - lo) / (hi - lo + 1e-9)
        pd_ = pk.rolling(d).mean()
        return round(float(pk.iloc[-1]), 1), round(float(pd_.iloc[-1]), 1)

    @staticmethod
    def ai_levels(df, price):
        c, h, l = df["Close"].dropna(), df["High"].dropna(), df["Low"].dropna()
        atr   = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1).tail(14).mean()
        ma20  = c.tail(20).mean()
        hi52  = h.tail(252).max()
        lo252 = l.tail(252).min()
        return dict(
            buy   = round(price * 1.003, 2),
            sell  = round(price + float(atr) * 2.0, 2),
            short_entry = round(price * 0.997, 2),           
            short_cover = round(price - float(atr) * 2.0, 2), 
            mid_t = round(max(float(h.tail(60).max()), price * 1.25), 2),
            lng_t = round(max(float(hi52), price * 1.60), 2),
            mid_d = round(min(float(l.tail(20).min()), float(ma20) * 0.95), 2),
            lng_d = round(float(lo252) * 1.05, 2),
            hi52  = float(hi52), atr = float(atr)
        )

    @staticmethod
    def risk_score(stoch_wk, vol_ratio, above_ma, sell_ratio):
        s, f = 0, {}
        if   stoch_wk >= 80: f["크게 오른 구간 (과열)"] = 20; s += 20
        elif stoch_wk >= 60: f["주봉 K 중상단"]          = 9;  s += 9
        else:                f["크게 눌린 구간"]          = 0
        
        if   vol_ratio > 1.5: f["거래량 급증"]            = 10; s += 10
        elif vol_ratio > 1.2: f["거래량 소폭 증가"]       = 5;  s += 5
        
        if not above_ma:      f["단기 이평 하방"]          = 10; s += 10
        else:                 f["단기 급등 구간"]          = 15; s += 15
        
        if sell_ratio > 0.3:  f["애널리스트 부정적"]       = 10; s += 10
        return min(s, 100), f

    @staticmethod
    def swing_signal(stoch_wk_k, stoch_wk_d, stoch_mk_k, stoch_mk_d,
                     mkt_wk_k, wk_ret, mo_ret, above_ma,
                     vol_ratio, from_hi, buy_ratio, sell_ratio):
        sigs = {}
        if   stoch_wk_k < 20 and stoch_wk_k > stoch_wk_d: sigs["주봉 스토 과매도 반등"] = +22
        elif stoch_wk_k < 20:                               sigs["주봉 스토 과매도"]     = +15
        elif stoch_wk_k > 80 and stoch_wk_k < stoch_wk_d: sigs["주봉 스토 과매수 꺾임"] = -22
        elif stoch_wk_k > 80:                               sigs["주봉 스토 과매수"]     = -15
        elif stoch_wk_k > stoch_wk_d:                       sigs["주봉 스토 상향교차"]   = +10
        else:                                                sigs["주봉 스토 하향교차"]   = -10
        if   stoch_mk_k < 25:         sigs["월봉 스토 과매도"]    = +15
        elif stoch_mk_k > 75:         sigs["월봉 스토 과매수"]    = -15
        elif stoch_mk_k > stoch_mk_d: sigs["월봉 스토 상승 추세"] = +8
        else:                         sigs["월봉 스토 하락 추세"] = -8
        if   mkt_wk_k < 25: sigs["시장 과매도 (역추세 기회)"] = +10
        elif mkt_wk_k > 75: sigs["시장 과매수 (경계)"]        = -8
        if   wk_ret >  5: sigs["주간 강한 상승 모멘텀"] = +8
        elif wk_ret >  2: sigs["주간 상승 모멘텀"]      = +5
        elif wk_ret < -5: sigs["주간 강한 하락 모멘텀"] = -8
        elif wk_ret < -2: sigs["주간 하락 모멘텀"]      = -5
        if   mo_ret > 10:  sigs["월간 강세 추세"] = +7
        elif mo_ret >  3:  sigs["월간 상승 추세"] = +4
        elif mo_ret < -10: sigs["월간 강한 하락"] = -7
        elif mo_ret <  -3: sigs["월간 하락 추세"] = -4
        sigs["이평선 위 (매수 우위)" if above_ma else "이평선 아래 (매도 우위)"] = +8 if above_ma else -8
        if   from_hi < -40: sigs["신고가 대비 깊은 조정 (반등 기대)"] = +10
        elif from_hi < -20: sigs["신고가 대비 조정 구간"]             = +4
        elif from_hi >  -5: sigs["신고가 근접 (추가 상승 제한)"]      = -6
        if vol_ratio > 1.3:
            sigs["거래량 증가 + 상승 (매수 압력)" if wk_ret > 0 else "거래량 증가 + 하락 (매도 압력)"] = +8 if wk_ret > 0 else -8
        net = buy_ratio - sell_ratio
        if   net > 0.5:  sigs["애널리스트 강한 매수 의견"] = +6
        elif net > 0.2:  sigs["애널리스트 매수 우위"]      = +3
        elif net < -0.2: sigs["애널리스트 매도 우위"]      = -6
        score = max(-100, min(100, sum(sigs.values())))
        key   = ("strong_long" if score >= 60 else "long" if score >= 20
                 else "strong_short" if score <= -60 else "short" if score <= -20 else "hodl")
        prob  = round(min(95, max(42, 40 + abs(score) * 0.55)), 1)
        return key, score, prob, sigs


# ── 3. App / UI Class ──────────────────────────────────────────────────────
class AInvestApp:
    """Streamlit 대시보드의 화면 구성과 전체 실행 흐름을 제어하는 클래스"""
    
    def __init__(self):
        self.data_manager = MarketDataManager()
        self.analyzer = StockAnalyzer()

    def setup_config(self):
        st.set_page_config(page_title="AInvest", page_icon="📈",
                           layout="wide", initial_sidebar_state="collapsed")
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
        html, body, .stApp { background-color:#0d0d1a !important; color:white;
            font-family:'Noto Sans KR',sans-serif; }
        .block-container { padding:1.2rem 1.5rem; max-width:860px; margin:auto; }
        .stButton > button {
            background:linear-gradient(135deg,#e05a00,#c94400) !important;
            color:white !important; border:none !important; border-radius:16px !important;
            font-size:18px !important; font-weight:900 !important;
            padding:18px 0 !important; width:100% !important; letter-spacing:1px; margin-top:8px;
        }
        .stButton > button:hover { opacity:0.9; }
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input {
            background:#1a1a2e !important; color:white !important;
            border:1px solid #2a2a40 !important; border-radius:12px !important;
            font-size:15px !important; padding:10px 14px !important;
        }
        .stTextInput label, .stNumberInput label { color:#888 !important; font-size:12px !important; }
        .card { background:#161626; border-radius:14px; padding:18px 20px; margin-bottom:10px; }
        .lbl  { font-size:12px; color:#888; margin-bottom:6px; }
        .sub  { font-size:12px; color:#666; margin-top:5px; }
        .divider { height:1px; background:#1e1e30; margin:14px 0; }
        .section-title { font-size:13px; font-weight:700; color:#555;
            letter-spacing:2px; text-transform:uppercase; margin:18px 0 8px; }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def stoch_html(label, k, d):
        clr   = "#e84040" if k >= d else "#4a9eff"
        arrow = "↑" if k >= d else "↓"
        pos   = max(2, min(97, k))
        return f"""<div class="card">
          <div class="lbl">{label}</div>
          <div style="font-size:28px;font-weight:900;color:{clr};margin-bottom:10px;">{arrow} {k}</div>
          <div style="position:relative;height:10px;border-radius:6px;
               background:linear-gradient(to right,#1e3a7a 0%,#1e3a7a 25%,#2a2a40 25%,#2a2a40 75%,#5a1a1a 75%);">
            <div style="position:absolute;left:{pos}%;top:50%;transform:translate(-50%,-50%);
                 width:16px;height:16px;border-radius:50%;background:{clr};box-shadow:0 0 6px {clr};"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#555;margin-top:4px;">
            <span>20</span><span>80</span>
          </div>
          <div style="font-size:11px;color:#555;margin-top:4px;">%K {k} · %D {d}</div>
        </div>"""

    @staticmethod
    def pct_bar_html(label, icon, price, pct, desc, ccy, positive=True):
        bar_bg = "#4a1a1a" if positive else "#1a2050"
        txt_c  = "#e84040" if positive else "#4a9eff"
        price_fmt = f"{ccy}{price:,.0f}" if ccy == "₩" else f"{ccy}{price:,.2f}"
        return f"""<div class="card">
          <div class="lbl">{icon} {label}</div>
          <div style="font-size:26px;font-weight:900;color:white;margin-bottom:6px;">{price_fmt}</div>
          <div style="background:{bar_bg};border-radius:5px;padding:4px 12px;display:inline-block;margin-bottom:8px;">
            <span style="color:{txt_c};font-weight:700;font-size:13px;">{pct:+.1f}%</span>
          </div>
          <div class="sub">{desc}</div>
        </div>"""

    @staticmethod
    def render_swing_card(key, score, prob, sigs, ticker):
        label, clr, tip = StockAnalyzer.SIGNAL_META[key]
        col_a, col_b = st.columns([3, 2])
        with col_a:
            st.markdown(f"""
            <div style="font-size:40px;font-weight:900;color:{clr};letter-spacing:1px;margin-bottom:4px;">{label}</div>
            <div style="font-size:13px;color:#666;">종합 스코어
              <span style="color:{clr};font-weight:700;">{score:+d} / 100</span>
            </div>""", unsafe_allow_html=True)
        with col_b:
            st.markdown(f"""
            <div style="text-align:right;">
              <div style="font-size:12px;color:#555;margin-bottom:2px;">판단 확률</div>
              <div style="font-size:58px;font-weight:900;color:{clr};line-height:1;">{prob}%</div>
            </div>""", unsafe_allow_html=True)
        cols = st.columns(5)
        for i, (skey, (slabel, sclr, _)) in enumerate(StockAnalyzer.SIGNAL_META.items()):
            active = (skey == key)
            bg     = sclr if active else "#1e1e30"
            border = f"2px solid {sclr}" if active else "2px solid #2a2a40"
            op     = "1" if active else "0.4"
            cols[i].markdown(f"""
            <div style="text-align:center;padding:8px 4px;border-radius:10px;
                 background:{bg};border:{border};opacity:{op};
                 height:52px;display:flex;flex-direction:column;
                 align-items:center;justify-content:center;">
              <div style="font-size:10px;font-weight:900;color:white;line-height:1.3;">
                {slabel.replace(' ', '<br>')}
              </div>
            </div>""", unsafe_allow_html=True)
        bar_left  = 50 if score >= 0 else 50 + score / 2
        bar_width = abs(score) / 2
        st.markdown(f"""
        <div style="margin:14px 0 10px;">
          <div style="background:#1e1e30;border-radius:6px;height:8px;position:relative;">
            <div style="position:absolute;left:50%;top:0;width:2px;height:8px;background:#333;"></div>
            <div style="position:absolute;left:{bar_left:.1f}%;width:{bar_width:.1f}%;
                 height:8px;border-radius:6px;background:{clr};"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:10px;color:#444;margin-top:4px;">
            <span>STRONG SHORT</span><span>HODL</span><span>STRONG LONG</span>
          </div>
        </div>""", unsafe_allow_html=True)
        is_short    = key in ("strong_short", "short")
        action_icon = "📉" if is_short else ("⏸" if key == "hodl" else "📈")
        action_txt  = (f"{ticker} 숏(Short) 포지션 진입{'을 강하게 권고합니다.' if key=='strong_short' else ' 검토.'}" if is_short
                       else (f"{ticker} 방향성 불명확 — 관망 후 재진입을 기다리세요." if key == "hodl"
                             else f"{ticker} 매수(Long) 포지션 진입{'을 강하게 권고합니다.' if key=='strong_long' else ' 우위 구간.'}"))
        st.markdown(f"""
        <div style="background:#0d0d1e;border-radius:10px;padding:12px 16px;margin:10px 0;">
          <div style="font-size:13px;font-weight:700;color:white;margin-bottom:4px;">{action_icon} {action_txt}</div>
          <div style="font-size:12px;color:{clr};">💡 {tip}</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div style='font-size:11px;color:#555;letter-spacing:1px;margin-bottom:6px;'>TOP 신호 요인</div>",
                    unsafe_allow_html=True)
        top5 = sorted([(k,v) for k,v in sigs.items() if v != 0], key=lambda x: abs(x[1]), reverse=True)[:5]
        for s_name, s_val in top5:
            s_clr  = "#30d158" if s_val > 0 else "#e84040"
            s_icon = "▲" if s_val > 0 else "▼"
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                 padding:7px 0;border-bottom:1px solid #1e1e30;font-size:13px;">
              <span style="color:#bbb;">{s_name}</span>
              <span style="color:{s_clr};font-weight:700;">{s_icon} {abs(s_val)}pt</span>
            </div>""", unsafe_allow_html=True)
        st.markdown("""
        <div style="margin-top:12px;font-size:11px;color:#3a3a4a;">
          ⚠️ 본 신호는 스윙트레이딩 참고용이며 투자 책임은 사용자에게 있습니다.
        </div></div>""", unsafe_allow_html=True)

    def run(self):
        self.setup_config()

        # ── Header ────────────────────────────────────────────────────────────
        st.markdown("""
        <div style="text-align:center;padding:24px 0 8px;">
          <div style="font-size:28px;font-weight:900;letter-spacing:1px;">📈 AInvest</div>
          <div style="font-size:13px;color:#555;margin-top:4px;">For STOCK </div>
          <div style="font-size:13px;color:#555;margin-top:4px;">Swing Trading </div>
        </div>""", unsafe_allow_html=True)

        # ── Input ─────────────────────────────────────────────────────────────
        c1, c2 = st.columns(2)
        with c1:
            seed_krw = st.number_input("💰 매수 시드 (원)", min_value=10_000,
                                        max_value=500_000_000, value=5_000_000,
                                        step=100_000, format="%d")
        with c2:
            raw_ticker = st.text_input("🔍 분석 종목 (티커)", value="",
                                       placeholder="예: AAPL, NVDA, 005930.KS")

        ticker_input = raw_ticker.upper().strip()
        is_korean, market_type, ccy, flag = self.data_manager.detect_market(ticker_input) if ticker_input else (False, "", "$", "🇺🇸")

        if ticker_input:
            st.markdown(f"""
            <div style="background:#1a2a1a;border-radius:10px;padding:10px 16px;
                 display:flex;align-items:center;gap:10px;margin-bottom:8px;">
              <span style="font-size:18px;">{flag}</span>
              <span style="font-weight:700;font-size:15px;">{ticker_input}</span>
              <span style="color:#888;font-size:12px;">· {market_type}</span>
              <span style="color:#30d158;font-size:13px;">✓ 선택됨</span>
            </div>""", unsafe_allow_html=True)

        run_btn = st.button("지금 분석하기 →", use_container_width=True)

        # ── Analysis ──────────────────────────────────────────────────────────
        if run_btn and ticker_input:
            with st.spinner("📡 데이터 수집 중 ..."):
                try:
                    t   = yf.Ticker(ticker_input)
                    inf = t.info
                    price  = inf.get("currentPrice") or inf.get("regularMarketPrice") or inf.get("previousClose", 0)
                    prev   = inf.get("previousClose") or price
                    chg    = price - prev
                    chg_pct= chg / prev * 100 if prev else 0
                    name   = inf.get("shortName") or inf.get("longName") or ticker_input
                    state_lbl = {"PRE":"🟡 프리마켓","REGULAR":"🟢 정규장",
                                 "POST":"🔵 애프터마켓","CLOSED":"⚫ 장 마감"}.get(
                                 inf.get("marketState","REGULAR"), "🟢 정규장")

                    # 통화 / 시드 계산
                    usd_krw = self.data_manager.get_fx()
                    if is_korean:
                        seed_trade = seed_krw
                        price_krw  = price
                    else:
                        seed_trade = seed_krw / usd_krw
                        price_krw  = price * usd_krw

                    # 시장 인덱스 데이터
                    if is_korean:
                        mkt_ticker_w = "^KS11" if market_type == "KOSPI" else "^KQ11"
                        mkt_ticker_m = mkt_ticker_w
                        mkt_label_w  = f"{market_type} 주간"
                        mkt_label_m  = f"{market_type} 월간"
                    else:
                        mkt_ticker_w = "QQQ"
                        mkt_ticker_m = "QQQ"
                        mkt_label_w  = "나스닥 주간 (QQQ 주봉)"
                        mkt_label_m  = "나스닥 월간 (QQQ 월봉)"

                    df_d  = self.data_manager.get_hist(ticker_input, "2y",  "1d")
                    df_wk = self.data_manager.get_hist(ticker_input, "3y",  "1wk")
                    df_mo = self.data_manager.get_hist(ticker_input, "5y",  "1mo")
                    mkt_w = self.data_manager.get_hist(mkt_ticker_w, "3y",  "1wk")
                    mkt_m = self.data_manager.get_hist(mkt_ticker_m, "5y",  "1mo")
                    spy_w = self.data_manager.get_hist("^KS11" if is_korean else "SPY", "3y", "1wk")

                    spy_k,  spy_d  = self.analyzer.calc_stoch(spy_w)
                    mktw_k, mktw_d = self.analyzer.calc_stoch(mkt_w)
                    mktm_k, mktm_d = self.analyzer.calc_stoch(mkt_m)
                    stk_wk, stk_wd = self.analyzer.calc_stoch(df_wk)
                    stk_mk, stk_md = self.analyzer.calc_stoch(df_mo)

                    spy_label = f"{'코스피' if is_korean else '시장'} 추세 ({'KOSPI' if is_korean else 'SPY'} 주봉)"

                    c_ = df_d["Close"]
                    wk_ret = (c_.iloc[-1]/c_.iloc[-6] -1)*100 if len(c_)>=6  else 0
                    mo_ret = (c_.iloc[-1]/c_.iloc[-22]-1)*100 if len(c_)>=22 else 0

                    lv = self.analyzer.ai_levels(df_d, price)

                    # 스윙 신호 1차 계산
                    sig_key, sig_score, sig_prob, sig_details = self.analyzer.swing_signal(
                        stk_wk, stk_wd, stk_mk, stk_md,
                        mktw_k, wk_ret, mo_ret, price > df_wk["Close"].tail(5).mean(),
                        df_d["Volume"].dropna().tail(5).sum() / max(df_d["Volume"].dropna().tail(100).sum()/20, 1),
                        (price/df_d["High"].tail(252).max()-1)*100,
                        0.6, 0.1
                    )
                    is_short_signal = sig_key in ("strong_short", "short")

                    # AI 매매전략 분기
                    if is_short_signal:
                        entry = lv["short_entry"]
                        cover = lv["short_cover"]
                        qty   = int(seed_trade / entry) if entry > 0 else 0
                        tot   = qty * entry
                        exp_r = (entry - cover) / entry * 100 if entry else 0
                        exp_profit_krw = qty * (entry - cover) * (1 if is_korean else usd_krw)
                        strategy_label_buy  = "숏 진입가 (AI)"
                        strategy_label_sell = "숏 커버가 (익절)"
                        buy_color  = "#4a9eff"
                        sell_color = "#30d158"
                        qty_label  = "수량 / 진입총액"
                    else:
                        entry = lv["buy"]
                        cover = lv["sell"]
                        qty   = int(seed_trade / entry) if entry > 0 else 0
                        tot   = qty * entry
                        exp_r = (cover - entry) / entry * 100 if entry else 0
                        exp_profit_krw = qty * (cover - entry) * (1 if is_korean else usd_krw)
                        strategy_label_buy  = "매수 진입가 (AI)"
                        strategy_label_sell = "매도 목표가 (AI)"
                        buy_color  = "#e84040"
                        sell_color = "#4a9eff"
                        qty_label  = "수량 / 총액"

                    mid_tp = (lv["mid_t"] - lv["buy"]) / lv["buy"] * 100
                    lng_tp = (lv["lng_t"] - lv["buy"]) / lv["buy"] * 100
                    mid_dp = (lv["mid_d"] - price) / price * 100
                    lng_dp = (lv["lng_d"] - price) / price * 100

                    vol       = df_d["Volume"].dropna()
                    vol_ratio = vol.tail(5).sum() / max(vol.tail(100).sum()/20, 1)
                    hi52      = df_d["High"].tail(252).max()
                    from_hi   = (price/hi52-1)*100
                    ma5w      = df_wk["Close"].tail(5).mean()
                    above_ma  = price > ma5w
                    ma5w_d    = (price-ma5w)/ma5w*100

                    try:
                        cal = t.calendar
                        if cal is not None and "Earnings Date" in cal:
                            ed  = cal["Earnings Date"]
                            ed  = ed[0] if isinstance(ed,(list,tuple)) else ed
                            ed  = pd.Timestamp(ed).date()
                            edd = (ed - date.today()).days
                        else:
                            ed = edd = None
                    except:
                        ed = edd = None

                    try:
                        ri = t.recommendations
                        gc = {"buy":0,"hold":0,"sell":0}
                        if ri is not None and len(ri):
                            for _, row in ri.tail(20).iterrows():
                                g = str(row.get("To Grade", row.get("Action",""))).lower()
                                if any(x in g for x in ["buy","outperform","overweight","strong"]):
                                    gc["buy"]+=1
                                elif any(x in g for x in ["sell","underperform","underweight"]):
                                    gc["sell"]+=1
                                else:
                                    gc["hold"]+=1
                        else:
                            gc = {"buy":3,"hold":11,"sell":1}
                    except:
                        gc = {"buy":3,"hold":11,"sell":1}
                    tc = sum(gc.values()) or 1

                    # 스윙 신호 재계산 (애널리스트)
                    sig_key, sig_score, sig_prob, sig_details = self.analyzer.swing_signal(
                        stk_wk, stk_wd, stk_mk, stk_md,
                        mktw_k, wk_ret, mo_ret, above_ma,
                        vol_ratio, from_hi, gc["buy"]/tc, gc["sell"]/tc
                    )
                    is_short_signal = sig_key in ("strong_short", "short")

                    if is_short_signal:
                        entry = lv["short_entry"]; cover = lv["short_cover"]
                        exp_r = (entry - cover) / entry * 100 if entry else 0
                        exp_profit_krw = qty * (entry - cover) * (1 if is_korean else usd_krw)

                    tmed  = inf.get("targetMedianPrice") or inf.get("targetMeanPrice") or 0
                    tlow  = inf.get("targetLowPrice")  or 0
                    thigh = inf.get("targetHighPrice") or 0
                    upside= (tmed/price-1)*100 if tmed and price else 0

                    rs, rf = self.analyzer.risk_score(stk_wk, vol_ratio, above_ma, gc["sell"]/tc)
                    r_lbl  = "저위험" if rs<=30 else ("중위험" if rs<=60 else "고위험")
                    r_clr  = "#30d158" if rs<=30 else ("#ff9500" if rs<=60 else "#e84040")
                    r_desc = ("매수 적합 구간. 상대적으로 안전해요." if rs<=30
                              else ("주의 구간. 분할 진입을 고려하세요." if rs<=60
                                    else "위험 구간. 신중하게 접근하세요."))

                    # ════════════ RENDER ══════════════════════════════════════
                    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

                    entry_fmt  = f"{ccy}{entry:,.0f}"  if is_korean else f"{ccy}{entry:,.2f}"
                    cover_fmt  = f"{ccy}{cover:,.0f}"  if is_korean else f"{ccy}{cover:,.2f}"
                    price_fmt  = f"{ccy}{price:,.0f}"  if is_korean else f"{ccy}{price:,.2f}"
                    prev_fmt   = f"{ccy}{prev:,.0f}"   if is_korean else f"{ccy}{prev:,.2f}"
                    chg_abs    = f"{ccy}{abs(chg):,.0f}" if is_korean else f"{ccy}{abs(chg):,.2f}"
                    chg_c = "#e84040" if chg>=0 else "#4a9eff"
                    arrow = "▲" if chg>=0 else "▼"

                    st.markdown(f"""
                    <div class="card">
                      <div class="lbl">{state_lbl} &nbsp;·&nbsp; {name} ({ticker_input}) &nbsp;·&nbsp; {market_type}</div>
                      <div style="font-size:38px;font-weight:900;color:white;margin:4px 0;">{price_fmt}</div>
                      <div style="font-size:14px;color:{chg_c};">
                        {arrow} {chg_abs} ({chg_pct:+.2f}%)
                        <span style="color:#555;font-size:12px;margin-left:12px;">전일종가 {prev_fmt}</span>
                      </div>
                      {"<div style='font-size:12px;color:#888;margin-top:6px;'>환율 기준 ≈ "+f"₩{price_krw:,.0f}"+"</div>" if not is_korean else ""}
                    </div>""", unsafe_allow_html=True)

                    st.markdown("<div class='section-title'>🎯 스윙 트레이딩 신호</div>", unsafe_allow_html=True)
                    self.render_swing_card(sig_key, sig_score, sig_prob, sig_details, ticker_input)

                    st.markdown("<div class='section-title'>📊 시장 추세</div>", unsafe_allow_html=True)
                    st.markdown(self.stoch_html(spy_label, spy_k, spy_d), unsafe_allow_html=True)
                    st.markdown(self.stoch_html(mkt_label_w, mktw_k, mktw_d), unsafe_allow_html=True)
                    st.markdown(self.stoch_html(mkt_label_m, mktm_k, mktm_d), unsafe_allow_html=True)

                    st.markdown(f"<div class='section-title'>📈 {ticker_input} 스토캐스틱</div>", unsafe_allow_html=True)
                    st.markdown(self.stoch_html(f"{ticker_input} 주간", stk_wk, stk_wd), unsafe_allow_html=True)
                    st.markdown(self.stoch_html(f"{ticker_input} 월간", stk_mk, stk_md), unsafe_allow_html=True)

                    st.markdown("<div class='section-title'>💡 AI 매매 전략</div>", unsafe_allow_html=True)

                    if is_short_signal:
                        short_clr = StockAnalyzer.SIGNAL_META[sig_key][1]
                        st.markdown(f"""
                        <div style="background:#0f0a1e;border:1px solid {short_clr};border-radius:10px;
                             padding:10px 16px;margin-bottom:10px;">
                          <span style="color:{short_clr};font-weight:700;font-size:13px;">
                            📉 숏(Short) 전략 기준으로 표시됩니다 — 인버스 포지션 매매가
                          </span>
                        </div>""", unsafe_allow_html=True)

                    tot_fmt = f"{ccy}{tot:,.0f}" if is_korean else f"₩{tot*usd_krw:,.0f}"
                    c1, c2 = st.columns(2)
                    with c1:
                        entry_offset = (entry/price-1)*100
                        st.markdown(f"""<div class="card">
                          <div class="lbl">{strategy_label_buy}</div>
                          <div style="font-size:30px;font-weight:900;color:{buy_color};">{entry_fmt}</div>
                          <div class="sub">진입가 ({entry_offset:+.1f}%)</div>
                        </div>""", unsafe_allow_html=True)
                    with c2:
                        cover_offset = (cover/price-1)*100
                        st.markdown(f"""<div class="card">
                          <div class="lbl">{strategy_label_sell}</div>
                          <div style="font-size:30px;font-weight:900;color:{sell_color};">{cover_fmt}</div>
                          <div class="sub">목표가 ({cover_offset:+.1f}%)</div>
                        </div>""", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"""<div class="card">
                          <div class="lbl">{qty_label}</div>
                          <div style="font-size:30px;font-weight:900;color:white;">{qty:,}주</div>
                          <div class="sub">≈ {tot_fmt}</div>
                        </div>""", unsafe_allow_html=True)
                    with c2:
                        ec = "#30d158" if exp_r >= 0 else "#e84040"
                        profit_sign = "+" if exp_profit_krw >= 0 else ""
                        st.markdown(f"""<div class="card">
                          <div class="lbl">예상 수익률</div>
                          <div style="font-size:30px;font-weight:900;color:{ec};">{exp_r:+.2f}%</div>
                          <div class="sub">{profit_sign}{exp_profit_krw/10000:.0f}만원</div>
                        </div>""", unsafe_allow_html=True)

                    st.markdown("<div class='section-title'>🎯 목표가 &amp; 방어선</div>", unsafe_allow_html=True)
                    st.markdown(self.pct_bar_html("중기 목표", "📅", lv["mid_t"], mid_tp, "이 가격을 돌파하면 추가 상승이 기대돼요", ccy), unsafe_allow_html=True)
                    st.markdown(self.pct_bar_html("장기 목표", "📅", lv["lng_t"], lng_tp, "상승 추세가 강할 때 노릴 수 있어요", ccy), unsafe_allow_html=True)
                    st.markdown(self.pct_bar_html("중기 방어선", "🛡️", lv["mid_d"], mid_dp, "이 가격 아래로 내려가면 추가 하락 위험이 있어요", ccy, False), unsafe_allow_html=True)
                    st.markdown(self.pct_bar_html("장기 방어선", "🔒", lv["lng_d"], lng_dp, "핵심 지지 구간 · 이탈 시 추세 전환 가능성", ccy, False), unsafe_allow_html=True)

                    st.markdown("<div class='section-title'>📐 기술적 지표</div>", unsafe_allow_html=True)
                    vol_c = "#ff9500" if vol_ratio>=1.3 else "white"
                    st.markdown(f"""<div class="card">
                      <div class="lbl">📊 이번 주 거래량</div>
                      <div style="font-size:30px;font-weight:900;color:{vol_c};">{vol_ratio:.1f}배</div>
                      <div class="sub">20주 평균 대비 · {'거래량이 늘었어요.' if vol_ratio>1.2 else '거래량 평균 수준이에요.'}</div>
                    </div>""", unsafe_allow_html=True)

                    prog_w = max(0, 100+from_hi)
                    hi_lbl = "반토막 이상" if from_hi<-50 else ("신고가 근접" if from_hi>-10 else "")
                    st.markdown(f"""<div class="card">
                      <div class="lbl">📉 52주 신고가 대비</div>
                      <div style="font-size:26px;font-weight:900;color:#4a9eff;">{from_hi:.1f}% {hi_lbl}</div>
                      <div style="background:#222;border-radius:4px;height:6px;margin:8px 0;">
                        <div style="width:{prog_w:.0f}%;background:#888;height:6px;border-radius:4px;"></div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    ma_c = "#e84040" if above_ma else "#4a9eff"
                    st.markdown(f"""<div class="card">
                      <div class="lbl">📊 5주 이동평균선</div>
                      <div style="font-size:24px;font-weight:900;color:{ma_c};">{'5주선 위 ↗' if above_ma else '5주선 아래 ↘'}</div>
                      <div style="background:{'#4a1a1a' if above_ma else '#1a2050'};border-radius:5px;
                           padding:3px 12px;display:inline-block;margin:6px 0;">
                        <span style="color:{ma_c};font-weight:700;">{ma5w_d:+.1f}%</span>
                      </div>
                      <div class="sub">{'단기 추세 살아있어요. 매수 우위.' if above_ma else '단기 추세 약화. 신중한 접근.'}</div>
                    </div>""", unsafe_allow_html=True)

                    earn_str = (f"D-{edd}" if edd and edd>0 else (f"D+{abs(edd)}" if edd and edd<0 else ("오늘!" if edd==0 else "미확인")))
                    st.markdown(f"""<div class="card">
                      <div class="lbl">📅 다음 실적 발표</div>
                      <div style="font-size:40px;font-weight:900;color:white;">{earn_str}</div>
                      <div class="sub">{str(ed) if ed else '일정 미확인'}</div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown("<div class='section-title'>🧑‍💼 애널리스트 컨센서스</div>", unsafe_allow_html=True)
                    tmed_fmt  = f"{ccy}{tmed:,.0f}"  if is_korean else f"{ccy}{tmed:,.2f}"
                    tlow_fmt  = f"{ccy}{tlow:,.0f}"  if is_korean else f"{ccy}{tlow:,.2f}"
                    thigh_fmt = f"{ccy}{thigh:,.0f}" if is_korean else f"{ccy}{thigh:,.2f}"
                    up_c = "#e84040" if upside>=0 else "#4a9eff"
                    st.markdown(f"""<div class="card">
                      <div style="display:flex;gap:24px;margin-bottom:10px;">
                        <div>
                          <div class="lbl">목표가 (중앙값)</div>
                          <div style="font-size:24px;font-weight:900;color:white;">{tmed_fmt}</div>
                        </div>
                        <div>
                          <div class="lbl">목표가 레인지</div>
                          <div style="font-size:16px;font-weight:700;color:white;margin-top:6px;">{tlow_fmt} ~ {thigh_fmt}</div>
                        </div>
                      </div>
                      <div style="color:{up_c};font-weight:700;font-size:14px;margin-bottom:10px;">{upside:+.1f}% 업사이드</div>
                      <div style="font-size:12px;color:#666;margin-bottom:6px;">
                        ({tc}명) &nbsp;
                        <span style="color:#e84040;">매수 {gc['buy']}</span> ·
                        <span style="color:#888;">보유 {gc['hold']}</span> ·
                        <span style="color:#4a9eff;">매도 {gc['sell']}</span>
                      </div>
                      <div style="background:#2a2a40;border-radius:5px;height:8px;overflow:hidden;">
                        <div style="display:flex;height:100%;">
                          <div style="width:{gc['buy']/tc*100:.0f}%;background:#e84040;"></div>
                          <div style="width:{gc['hold']/tc*100:.0f}%;background:#444;"></div>
                          <div style="width:{gc['sell']/tc*100:.0f}%;background:#4a9eff;"></div>
                        </div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown("<div class='section-title'>🛡️ 리스크 스코어</div>", unsafe_allow_html=True)
                    factors_html = "".join([
                        f"""<div style="display:flex;justify-content:space-between;padding:6px 0;
                            border-bottom:1px solid #1e1e30;font-size:13px;">
                          <span style="color:#ccc;">{k}</span>
                          <span style="color:#{'30d158' if v==0 else 'e84040'};font-weight:700;">
                            {'+'+str(v) if v>0 else str(v)}
                          </span></div>"""
                        for k, v in rf.items()
                    ])
                    st.markdown(f"""<div class="card">
                      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                        <span style="font-size:36px;font-weight:900;color:{r_clr};">{rs}</span>
                        <span style="color:#555;font-size:14px;">/100</span>
                        <span style="font-size:16px;font-weight:900;color:{r_clr};">{r_lbl}</span>
                      </div>
                      <div class="sub" style="margin-bottom:10px;">{r_desc}</div>
                      <div style="background:#2a2a40;border-radius:5px;height:8px;margin-bottom:14px;">
                        <div style="width:{rs}%;background:{r_clr};border-radius:5px;height:8px;"></div>
                      </div>
                      <div style="font-size:12px;color:#555;margin-bottom:6px;">기여 요소</div>
                      {factors_html}
                    </div>""", unsafe_allow_html=True)

                    st.markdown("""
                    <div style="background:#0f0f1e;border:1px solid #2a2a40;border-radius:10px;
                         padding:12px 16px;margin-top:16px;font-size:12px;color:#555;">
                      ⚠️ 본 분석은 투자 참고용이며 투자 결정의 책임은 사용자에게 있습니다.
                    </div>""", unsafe_allow_html=True)

                except Exception as e:
                    st.markdown("""
                    <div style="background:#1a0f0f;border:1px solid #e84040;border-radius:14px;
                         padding:20px 22px;margin-top:12px;">
                      <div style="font-size:16px;font-weight:900;color:#e84040;margin-bottom:12px;">
                        ⚠️ 종목을 찾을 수 없어요
                      </div>
                      <div style="font-size:13px;color:#aaa;line-height:2;margin-bottom:14px;">
                        티커 심볼을 다시 확인해주세요.<br>
                        한글 종목명으로는 검색이 되지 않아요.
                      </div>
                      <div style="background:#0f0f1e;border-radius:10px;padding:14px 16px;">
                        <div style="font-size:12px;color:#ff9500;font-weight:700;
                             margin-bottom:10px;letter-spacing:1px;">💡 검색 TIP</div>
                        <div style="font-size:12px;color:#888;line-height:2.4;">
                          🇺🇸 &nbsp;미국 주식 &nbsp;&nbsp;→&nbsp;
                            <span style="color:white;font-weight:700;">AAPL, NVDA, TSLA</span><br>
                          🇰🇷 &nbsp;코스피 &nbsp;&nbsp;&nbsp;&nbsp;→&nbsp;
                            <span style="color:white;font-weight:700;">005930.KS</span>
                            <span style="color:#555;">&nbsp;(삼성전자)</span><br>
                          🇰🇷 &nbsp;코스닥 &nbsp;&nbsp;&nbsp;&nbsp;→&nbsp;
                            <span style="color:white;font-weight:700;">035720.KQ</span>
                            <span style="color:#555;">&nbsp;(카카오)</span><br>
                          📊 &nbsp;ETF &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→&nbsp;
                            <span style="color:white;font-weight:700;">QQQ, SPY, SOXS</span>
                        </div>
                      </div>
                    </div>""", unsafe_allow_html=True)


# ── Entry Point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AInvestApp()
    app.run()