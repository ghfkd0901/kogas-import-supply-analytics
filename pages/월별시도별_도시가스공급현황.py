# app_kogas_monthly.py
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ======================
# 기본 설정
# ======================
st.set_page_config(page_title="한국가스공사 월별 시도별 판매현황", layout="wide")
st.title("한국가스공사 월별 · 시도별 도시가스 판매현황")
st.caption("원본: 한국가스공사 월별 시도별 도시가스 판매현황 CSV")

# ---- 상대경로로 수정 ----
# (현재 파일: pages/월별시도별_도시가스공급현황.py → 상위 폴더가 프로젝트 루트)
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "data" / "한국가스공사_한국가스공사_월별 시도별 도시가스 판매현황_20221231.csv"

FILE_PATH = DATA_PATH

# ======================
# 데이터 로드 함수
# ======================
@st.cache_data(ttl=3600)
def load_data(path: Path) -> pd.DataFrame:
    # 인코딩 자동 처리 (utf-8 → 안되면 cp949)
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp949")

    # wide → long (melt)
    region_cols = [c for c in df.columns if c != "연월"]
    df_long = df.melt(
        id_vars="연월",
        value_vars=region_cols,
        var_name="시도",
        value_name="판매량",
    )

    # 숫자형 강제 변환(쉼표 등 처리)
    df_long["판매량"] = pd.to_numeric(df_long["판매량"], errors="coerce")

    # 연월을 datetime으로 변환 (YYYY-MM)
    df_long["연월"] = pd.to_datetime(df_long["연월"], format="%Y-%m", errors="coerce")

    # 연도 / 월 컬럼 추가 (필터용)
    df_long["연도"] = df_long["연월"].dt.year
    df_long["월"] = df_long["연월"].dt.month

    # 정렬
    df_long = df_long.dropna(subset=["연월"]).sort_values(["연월", "시도"]).reset_index(drop=True)
    return df_long


data = load_data(FILE_PATH)

# ======================
# 사이드바 필터
# ======================
st.sidebar.header("⚙️ 필터")

# ▶ 연월 범위 슬라이더 (YYYY-MM)
min_date = data["연월"].min()
max_date = data["연월"].max()
date_range = st.sidebar.slider(
    "연월 범위 선택 (YYYY-MM)",
    min_value=min_date.to_pydatetime(),
    max_value=max_date.to_pydatetime(),
    value=(min_date.to_pydatetime(), max_date.to_pydatetime()),
    format="YYYY-MM",
)

# 시도 선택 (멀티)
regions_all = sorted(data["시도"].unique())
selected_regions = st.sidebar.multiselect(
    "시도 선택",
    options=regions_all,
    default=regions_all,  # 기본: 전체 시도
)

# Top N (기간 합계 기준)
max_n = max(1, len(selected_regions))
top_n = st.sidebar.slider("Top N (기간 합계 기준)", min_value=1, max_value=max_n, value=min(10, max_n), step=1)

# ======================
# 필터 적용
# ======================
start_dt, end_dt = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

df_filtered = data[(data["연월"] >= start_dt) & (data["연월"] <= end_dt)].copy()
if selected_regions:
    df_filtered = df_filtered[df_filtered["시도"].isin(selected_regions)]

# Top N 추출: 선택 구간 내 합계 기준
if not df_filtered.empty:
    top_regions = (
        df_filtered.groupby("시도", as_index=False)["판매량"].sum()
        .sort_values("판매량", ascending=False)
        .head(top_n)["시도"]
        .tolist()
    )
    df_filtered = df_filtered[df_filtered["시도"].isin(top_regions)]

# ======================
# 상단: 월별 꺾은선 그래프
# ======================
st.subheader("📈 월별 시도별 판매량 추이 (꺾은선 그래프)")
if df_filtered.empty:
    st.warning("선택된 조건에 해당하는 데이터가 없습니다. 필터를 조정해보세요.")
else:
    fig_line = px.line(
        df_filtered,
        x="연월",
        y="판매량",
        color="시도",
        markers=True,
        title="월별 시도별 판매량 추이",
    )
    fig_line.update_layout(
        xaxis_title="연월",
        yaxis_title="판매량",
        hovermode="x unified",
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ======================
# 중단: 월별 스택드 막대그래프 (누적영역 대체)
# ======================
st.subheader("🧱 월별 시도별 스택드 막대 (합계)")
if df_filtered.empty:
    st.info("표시할 데이터가 없습니다.")
else:
    # 월별-시도별 합계(이미 월별 단위면 동일하지만, 안전하게 groupby)
    df_monthly = (
        df_filtered.groupby(["연월", "시도"], as_index=False)["판매량"].sum()
        .sort_values(["연월", "시도"])
    )
    fig_bar = px.bar(
        df_monthly,
        x="연월",
        y="판매량",
        color="시도",
        title="월별 시도별 판매량 — 스택드 막대",
    )
    fig_bar.update_layout(
        barmode="stack",
        xaxis_title="연월",
        yaxis_title="판매량",
        hovermode="x unified",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ======================
# 하단: 데이터 영역
# ======================
st.divider()
st.subheader("🔎 필터 적용된 데이터 (현재 그래프 기준)")

if df_filtered.empty:
    st.info("표시할 데이터가 없습니다.")
else:
    st.dataframe(
        df_filtered.sort_values(["연월", "시도"]).reset_index(drop=True),
        use_container_width=True,
        height=420,
    )

with st.expander("📋 전체 long-form 데이터 보기 (melt 결과 전체)"):
    st.dataframe(
        data.sort_values(["연월", "시도"]).reset_index(drop=True),
        use_container_width=True,
        height=500,
    )
