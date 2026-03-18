━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 장기국고채 마켓 데일리 자동 분석기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[설치 방법]

1. Python 3.10 이상 설치
   https://www.python.org/downloads/

2. 이 폴더에서 터미널/CMD 열기

3. 패키지 설치:
   pip install -r requirements.txt


[실행 방법]

   streamlit run app.py

   → 브라우저가 자동으로 열립니다 (http://localhost:8501)


[사용 방법]

1. 왼쪽 사이드바에서 엑셀 파일 업로드
2. 기준 종목 선택 (기본: 25-7)
3. Q6, Q12 파라미터 설정

4개 탭:
  - 분석 결과: 12개 질문 자동 답변
  - 편집 가능 리포트: 텍스트로 편집/복사/다운로드
  - 차트: Q4 이동평균, Q11 스프레드 (인터랙티브)
  - 추가 질문: 자연어로 데이터 질의


[파일 구조]

  app.py          — Streamlit 웹 앱 (메인)
  bond_engine.py  — 분석 엔진 (12개 질문 + Q&A)
  requirements.txt — 의존성 패키지
  README.txt      — 이 파일


[한글 폰트]

Windows/macOS에서는 자동으로 맑은고딕/AppleGothic 사용.
Linux에서는 아래 설치 후 사용:
  sudo apt install fonts-nanum


[문의]

mooniboy@naver.com
010-5201-6219
