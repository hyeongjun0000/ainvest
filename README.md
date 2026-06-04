2026 - 1 OSS Project

<br>

<div align="center">
  <h1>📈 AInvest : AI + Invest</h1>
  <p><b>Advanced Stock Swing Trading Dashboard with AI Signals</b></p>
  
  [![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)]()
  [![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)]()
  [![yfinance](https://img.shields.io/badge/yfinance-API-00B140?style=flat-square)]()
</div>

---

## 💡 About The Project

최근 금융 시장은 실시간 뉴스, 기업 실적, 경제 지표 등 방대한 정보가 끊임없이 생성되고 있습니다. 초보 투자자의 경우 RSI, MACD, 스토캐스틱 등 복잡한 기술적 지표를 직접 수집하고 해석하여 올바른 투자 결정을 내리는 데 큰 진입 장벽을 느낍니다.

**AInvest**는 이러한 문제를 해결하기 위해 개발된 시스템입니다. 실시간 금융 데이터 수집 기술과 알고리즘을 결합하여, 사용자가 종목 티커(Ticker)와 시드 머니를 입력하는 것만으로 **현재 시장 상황, 기술적 지표 상태, AI 기반 매수/매도 신호 및 예상 목표가**를 한눈에 확인할 수 있도록 의사결정을 단순화해 줍니다.

## ✨ Key Features

* 🌍 **다중 시장 지원**: 한국(KOSPI, KOSDAQ) 및 미국(NASDAQ, NYSE) 주식 실시간 데이터 분석
* 🤖 **AI 매매 전략 (Trading Strategy)**: LONG / SHORT / HODL 신호 제공 및 진입가, 목표가, 방어선(손절가) 자동 산출
* 📉 **기술적 분석 자동화 (Technical Indicators)**: 스토캐스틱, RSI, 거래량 배수, 이동평균선(MA), 신고가 대비 등락률 계산
* ⚠️ **리스크 매니지먼트 (Risk Score)**: 기술적/정성적 요소를 점수화한 시장 위험도 지표 제공
* 💼 **컨센서스 및 실적 추적**: 애널리스트 목표가 범위, 매매 의견 수집 및 다음 실적 발표일(D-Day) 분석
* 🛡️ **하락장 대응 (Inverse Strategy)**: 시장 하락 추세 감지 및 숏(Short) 신호 발생 시 인버스 ETF 전략 가이드 제공

---

## 🖥️ User Interface (Screenshots)

| 메인 대시보드 (Main) | 매매 전략 및 지표 (Strategy & Indicators) |
| :---: | :---: |
| <img src="./images/4-1,2.png" alt="Main UI" width="400"/> | <img src="./images/4-4.png" alt="Trading Strategy" width="400"/> |
| 투자 시드 및 티커 입력, 종목 요약 정보 제공 | AI 기반 중장기 목표가, 방어선 및 투자 수량 제안 |

*(※ 스크린샷 경로는 실제 프로젝트 이미지 환경에 맞게 수정하여 사용하세요.)*

---

## 🛠️ Tech Stack & Architecture

### Environment
* **Language**: Python 3.10+
* **Framework**: Streamlit (웹 대시보드 UI 및 프레젠테이션 레이어)
* **Data Source**: `yfinance` API (실시간 주가, 메타데이터, 컨센서스)
* **Data Processing**: `pandas`, `numpy`

### System Architecture
본 시스템은 단일 `app.py`로 구동되지만 역할에 따라 3개의 핵심 클래스로 분리되어 설계되었습니다.
1.  **`MarketDataManager`**: 시장 판별(국내/해외) 및 실시간 가격, 환율, 과거 시계열 데이터 수집 담당
2.  **`StockAnalyzer`**: 기술 지표(Stochastic, ATR 등) 계산, AI 매매 레벨 산출, 리스크 스코어링 담당
3.  **`AInvestApp`**: Streamlit 기반의 화면 제어, 데이터 로딩 상태 관리, UI 오케스트레이션 총괄

---

## 🚀 Getting Started

### Prerequisites
로컬 환경에서 AInvest를 실행하기 위해 파이썬 패키지 설치가 필요합니다.

```bash
# 저장소 클론
git clone [https://github.com/yourusername/AInvest.git](https://github.com/yourusername/AInvest.git)
cd AInvest

# 필수 라이브러리 설치
pip install -r requirements.txt
