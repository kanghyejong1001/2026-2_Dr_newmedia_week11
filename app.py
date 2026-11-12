import io
import contextlib

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from database import init_db, create_user, login_user, insert_survey_data, fetch_survey_data
import history
import menu_order

# DB 초기화 및 테이블 생성
init_db()

st.set_page_config(
    page_title="AI 교육 앱", page_icon="🎓", layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- 공통 정의
GAME_MENUS = list(menu_order.DEFAULT_GAME_MENUS)  # 체류 시간 측정 대상 게임 메뉴 3가지
GAME_META = {
    "pythonid": {"label": "파이썬 학습", "icon": "🐍", "desc": "내장 파이썬 실행기로 바로 실습"},
    "블록리게임": {"label": "블록리게임", "icon": "🧩", "desc": "Blockly 퍼즐 · 미로 · 거북이"},
    "테트리스게임": {"label": "테트리스게임", "icon": "🎮", "desc": "테트리스로 두뇌 휴식"},
}


def fmt_duration(seconds) -> str:
    seconds = float(seconds or 0)
    if seconds < 60:
        return f"{seconds:.1f}초"
    minutes, sec = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes}분 {sec}초"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}시간 {minutes}분"


# ---------------------------------------------------------------- 테마 적응형 커스텀 CSS
# Streamlit 기본 테마(라이트/다크 = PC 설정) 변수를 사용해 양쪽 테마 모두 자동 대응
st.markdown("""
<style>
    /* 사이드바 메뉴 카드(버튼) */
    div[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid transparent;
        background: var(--secondary-background-color);
        color: var(--text-color);
        text-align: left;
        padding: 0.6rem 1rem;
        font-size: 0.98rem;
        transition: all .15s ease;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        border-color: var(--primary-color);
        transform: translateX(3px);
    }
    div[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        border-color: var(--primary-color);
        box-shadow: inset 4px 0 0 var(--primary-color);
        font-weight: 700;
    }
    div[data-testid="stSidebar"] .stButton > button p { font-size: 0.98rem; }

    /* 사이드바 섹션 헤더 */
    .nav-section {
        font-size: 0.8rem; font-weight: 800; letter-spacing: .08em;
        opacity: .65; margin: .8rem 0 .3rem 0; text-transform: uppercase;
    }

    /* 본문 카드 */
    .app-card {
        border-radius: 16px;
        background: var(--secondary-background-color);
        padding: 1.2rem 1.5rem;
        border: 1px solid rgba(127,127,127,.25);
        margin-bottom: 1rem;
    }
    .app-card h3, .app-card h4 { margin-top: 0; }

    /* 순위 배지 */
    .rank-chip {
        display: inline-block; min-width: 1.6em; text-align: center;
        border-radius: 8px; padding: .1em .5em; font-weight: 700;
        background: var(--primary-color); color: #fff; margin-right: .5em;
    }
    .muted { opacity: .7; font-size: .9rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- 세션/네비게이션
def _clear_session():
    for key in ("game_order", "current_menu", "visit_id", "visit_started_at"):
        st.session_state.pop(key, None)


def _go(page: str):
    def callback():
        st.session_state["page"] = page
    return callback


def _logout():
    """로그아웃 콜백: 진행 중인 체류 시간을 먼저 확정하고 세션을 비운다."""
    history.finish_visit(
        st.session_state.get("visit_id"), st.session_state.get("visit_started_at")
    )
    _clear_session()
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""
    st.session_state["page"] = "Home"


def _login(userid: str):
    """로그인 성공: 학습 이력 기반으로 게임 메뉴 순서를 재배치한다 (기능 4)."""
    _clear_session()
    st.session_state["logged_in"] = True
    st.session_state["user_id"] = userid
    st.session_state["page"] = "Home"
    st.session_state["game_order"] = menu_order.ordered_game_menus(userid)


def _refresh_order(user_id: str):
    """머문 시간이 바뀔 때마다 메뉴 순서를 다시 계산 (체류 시간 → 순서 반영)."""
    st.session_state["game_order"] = menu_order.ordered_game_menus(user_id)


def _track_menu(user_id: str, page: str):
    """페이지가 바뀐 순간에만 호출 (재실행마다 중복 기록 방지).

    게임 메뉴 3가지에만 기록:
    - 게임 메뉴에 들어가는 순간  : waiting_time=0 행 INSERT
    - 다른 메뉴로 떠나는 순간    : 체류 시간(초) UPDATE 후 메뉴 순서 재계산
    """
    previous = st.session_state.get("current_menu")
    if previous == page:
        return

    if previous in GAME_MENUS:
        seconds = history.finish_visit(
            st.session_state.get("visit_id"), st.session_state.get("visit_started_at")
        )
        _refresh_order(user_id)
        st.toast(f"{GAME_META[previous]['icon']} {GAME_META[previous]['label']} · 체류 {seconds}초 저장 — 메뉴 순서가 갱신되었습니다", icon="💾")

    st.session_state["current_menu"] = page
    if page in GAME_MENUS:
        visit_id, started_at = history.start_visit(user_id, page)
        st.session_state["visit_id"] = visit_id
        st.session_state["visit_started_at"] = started_at
    else:
        st.session_state["visit_id"] = None
        st.session_state["visit_started_at"] = None


if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""
if "page" not in st.session_state:
    st.session_state["page"] = "Home"

page = st.session_state["page"]

# ---------------------------------------------------------------- 사이드바
user_id = st.session_state["user_id"]

with st.sidebar:
    st.markdown("## 🎓 AI 교육 앱")
    st.caption("AI의 교육적 효과를 경험하고 설문으로 인식을 나눠요.")

    if not st.session_state["logged_in"]:
        # 로그인 전: 계정 화면 안내만 표시 (게임/설문 메뉴는 숨김)
        st.divider()
        st.info("로그인 후 게임 메뉴와 설문에 참여할 수 있어요.", icon="🔒")

    else:
        # 👤 계정 카드
        st.markdown(f"""
        <div class="app-card" style="padding:.8rem 1rem;">
            <b>{user_id}</b> 님 환영합니다 👋<br>
            <span class="muted">총 학습 {fmt_duration(history.total_seconds(user_id))}</span>
        </div>
        """, unsafe_allow_html=True)
        st.button("🚪 로그아웃", on_click=_logout, use_container_width=True)

        # 🏠 홈 (독립 섹션)
        st.markdown('<div class="nav-section">🏠 시작</div>', unsafe_allow_html=True)
        st.button("홈 대시보드", on_click=_go("Home"), use_container_width=True, type="primary" if page == "Home" else "secondary")

        # 🎮 게임 메뉴 (머문 시간 기준 실시간 정렬)
        st.markdown('<div class="nav-section">🎮 게임 메뉴</div>', unsafe_allow_html=True)
        order = st.session_state.get("game_order") or menu_order.ordered_game_menus(user_id)
        stats = history.menu_stats(user_id)
        st.caption(f"⏱️ 누적 체류 시간이 많은 순으로 자동 정렬 ({menu_order.STRATEGY_LABELS[menu_order.ORDER_STRATEGY]})")
        for i, m in enumerate(order):
            dwell = fmt_duration(stats.get(m, {}).get("total", 0))
            st.button(
                f"{GAME_META[m]['icon']} {GAME_META[m]['label']}",
                key=f"nav_{m}",
                on_click=_go(m),
                use_container_width=True,
                type="primary" if page == m else "secondary",
                help=f"현재 {i+1}순위 · 누적 체류 {dwell} · {GAME_META[m]['desc']}",
            )

        # 📝 설문 (하단 독립 섹션)
        st.divider()
        st.markdown('<div class="nav-section">📝 설문</div>', unsafe_allow_html=True)
        st.button("설문 참여하기", on_click=_go("설문참여"), use_container_width=True, type="primary" if page == "설문참여" else "secondary")

page = st.session_state["page"]

# 체류 시간 추적 (게임 메뉴 3가지에만 기록)
if st.session_state["logged_in"]:
    _track_menu(user_id, page)

# ---------------------------------------------------------------- 로그인 전 화면
if not st.session_state["logged_in"]:
    st.markdown("### 🎓 AI 교육 앱에 오신 것을 환영합니다")
    st.caption("계정 메뉴에서 로그인하거나 새 계정을 만들어 주세요.")

    tab_login, tab_join = st.tabs(["로그인", "회원가입"])

    with tab_login:
        with st.form("login_form", clear_on_submit=True):
            userid = st.text_input("ID")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if submit:
            result = login_user(userid, password)
            if result:
                _login(userid.strip())
                st.rerun()
            else:
                st.error("ID 또는 비밀번호가 틀렸습니다.")

    with tab_join:
        with st.form("signup_form", clear_on_submit=True):
            new_user = st.text_input("ID")
            new_name = st.text_input("Name")
            new_password = st.text_input("Password", type="password")
            new_email = st.text_input("Email")
            submit = st.form_submit_button("가입하기", type="primary", use_container_width=True)
        if submit:
            ok, message = create_user(new_user, new_name, new_password, new_email)
            if ok:
                st.success(message + " 상단 로그인 탭에서 로그인해 주세요.")
            else:
                st.error(f"오류: {message}")

    st.stop()

# ---------------------------------------------------------------- 홈 대시보드
if page == "Home":
    stats = history.menu_stats(user_id)
    order = st.session_state.get("game_order") or menu_order.ordered_game_menus(user_id)
    total = history.total_seconds(user_id)
    visits = sum(v["visits"] for v in stats.values())
    top_game = order[0] if order else None

    st.title(f"📊 {user_id}님의 학습 대시보드")
    st.caption("게임 메뉴의 체류 시간이 자동으로 기록되고, 머문 시간에 따라 메뉴 순서가 바뀝니다.")

    c1, c2, c3 = st.columns(3)
    c1.metric("총 학습 시간", fmt_duration(total))
    c2.metric("총 방문 횟수", f"{visits}회")
    c3.metric("가장 몰입한 게임", f"{GAME_META[top_game]['icon']} {GAME_META[top_game]['label']}" if top_game and stats.get(top_game) else "-")

    st.divider()

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("게임별 누적 체류 시간")
        chart_df = pd.DataFrame(
            [{"게임": f"{GAME_META[m]['icon']} {GAME_META[m]['label']}", "누적 체류(초)": stats.get(m, {}).get("total", 0.0)} for m in GAME_MENUS]
        ).set_index("게임")
        if chart_df["누적 체류(초)"].sum() > 0:
            st.bar_chart(chart_df)
        else:
            st.info("아직 학습 기록이 없습니다. 게임 메뉴를 클릭하면 체류 시간이 기록됩니다.", icon="🕹️")

    with right:
        st.subheader("현재 메뉴 순서")
        st.caption("머문 시간을 기록할 때마다 이 순서가 자동으로 바뀝니다.")
        for i, m in enumerate(order):
            dwell = fmt_duration(stats.get(m, {}).get("total", 0))
            st.markdown(
                f'<div class="app-card" style="padding:.55rem 1rem;">'
                f'<span class="rank-chip">{i+1}</span>'
                f"{GAME_META[m]['icon']} <b>{GAME_META[m]['label']}</b>"
                f'<span class="muted" style="float:right;">⏱ {dwell}</span></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.subheader("최근 학습 기록")
    conn_rows = []
    for m in GAME_MENUS:
        for r in history.recent_visits(user_id, m, limit=5):
            conn_rows.append({
                "게임": f"{GAME_META[m]['icon']} {GAME_META[m]['label']}",
                "클릭 시각": (r["created_at"] or "").replace("T", " ")[:19],
                "체류 시간(초)": r["waiting_time"],
            })
    if conn_rows:
        df = pd.DataFrame(conn_rows).sort_values("클릭 시각", ascending=False)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.caption("아직 기록이 없습니다.")

# ---------------------------------------------------------------- 파이썬 학습 (내장 실행기)
elif page == "pythonid":
    st.title("🐍 파이썬 학습")
    st.info("현재 이 메뉴의 체류 시간을 측정 중입니다. 다른 메뉴를 선택하거나 로그아웃하면 초 단위로 저장됩니다.", icon="⏱️")

    # st.markdown("""
    # <div class="app-card">
    #     <h4>왜 iframe에서 열리지 않았나?</h4>
    #     <p class="muted">기존에 사용한 online-python.com 은 <code>X-Frame-Options: SAMEORIGIN</code> 헤더를 보내
    #     다른 사이트 안에 iframe으로 넣는 것을 서버 차원에서 금지합니다. 그래서 화면이 비어 보였던 것입니다.
    #     그래서 앱 안에 <b>직접 실행되는 파이썬 편집기를 내장</b>했습니다.</p>
    # </div>
    # """, unsafe_allow_html=True)

    DEFAULT_CODE = '''# 코드를 수정하고 [▶ 실행] 버튼을 눌러보세요
name = "AI 교육"
for i in range(1, 4):
    print(f"{i}번째 시간: {name} 수업!")

nums = [10, 25, 3, 47, 8]
print("최댓값:", max(nums))'''

    code = st.text_area("파이썬 코드 편집기", DEFAULT_CODE, height=340)
    run = st.button("▶ 실행", type="primary")
    if run:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, {"__name__": "__main__"})
            out = buf.getvalue()
            st.success("실행 완료!")
            st.code(out if out.strip() else "(출력 없음)", language="text")
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
            if buf.getvalue():
                st.code(buf.getvalue(), language="text")
    st.caption("※ `input()` 키보드 입력은 지원하지 않습니다. 브라우저에서 바로 실행되는 간단 실행기입니다.")

    st.markdown("[🔗 새 창에서 온라인 컴파일러 열기](https://www.online-python.com/)")

# ---------------------------------------------------------------- 블록리게임
elif page == "블록리게임":
    st.title("🧩 블록리게임 (Blockly Games)")
    st.caption("블록 코딩으로 퍼즐·미로·새·거북이 등 단계별 게임을 해결해 보세요.")
    st.info("현재 이 메뉴의 체류 시간을 측정 중입니다. 다른 메뉴를 선택하거나 로그아웃하면 초 단위로 저장됩니다.", icon="⏱️")
    components.html(
        '<iframe src="https://blockly.games/?lang=ko" title="Blockly Games" '
        'width="100%" height="600" style="border:none;border-radius:12px;" '
        'allow="fullscreen" allowfullscreen></iframe>',
        height=615, scrolling=True,
    )
    st.markdown("[🔗 새 창에서 열기](https://blockly.games/?lang=ko)")

# ---------------------------------------------------------------- 테트리스게임
elif page == "테트리스게임":
    st.title("🎮 테트리스게임 (Tetris)")
    st.caption("게임 화면을 한 번 클릭한 뒤 키보드 방향키(←→↓↑)와 스페이스바로 플레이하세요.")
    st.info("현재 이 메뉴의 체류 시간을 측정 중입니다. 다른 메뉴를 선택하거나 로그아웃하면 초 단위로 저장됩니다.", icon="⏱️")
    components.html(
        '<iframe src="https://play.tetris.com/" title="Tetris" '
        'width="100%" height="600" style="border:none;border-radius:12px;" '
        'allow="fullscreen; autoplay; gamepad" allowfullscreen></iframe>',
        height=615, scrolling=True,
    )
    st.markdown("[🔗 새 창에서 열기](https://play.tetris.com/)")

    st.divider()
    st.subheader("이 게임의 학습 기록")
    stats = history.menu_stats(user_id)
    menu_stat = stats.get("테트리스게임") or {"visits": 0, "total": 0.0}
    visits, total = menu_stat["visits"], menu_stat["total"]
    c1, c2, c3 = st.columns(3)
    c1.metric("방문 횟수", f"{visits}회")
    c2.metric("누적 체류", fmt_duration(total))
    c3.metric("평균 체류", fmt_duration(total / visits if visits else 0))

# ---------------------------------------------------------------- 설문참여
elif page == "설문참여":
    st.title("📝 AI의 교육적 효과에 대한 인식 설문조사")

    tab1, tab2 = st.tabs(["📋 설문응시", "📊 설문결과 시각화"])

    questions = [
        "1. AI는 학습자의 학업 성취도를 향상시키는 데 도움이 된다.",
        "2. AI는 개별 학습자의 수준에 맞춘 맞춤형 학습을 제공하는 데 효과적이다.",
        "3. AI를 활용한 교육은 학습자의 흥미와 참여도를 높인다.",
        "4. AI는 교사의 업무 부담을 줄이고 교육의 질을 높이는 데 기여한다.",
        "5. AI 기반 평가 시스템은 공정하고 객관적인 결과를 제공한다.",
        "6. AI 교육 도구는 자기주도적 학습 능력을 기르는 데 유용하다.",
        "7. 교육 현장에서 AI를 도입하는 것은 필수적인 흐름이다.",
        "8. AI는 복잡한 개념이나 원리를 이해하는 데 도움을 준다.",
        "9. AI 활용 교육은 창의력과 문제해결능력 향상에 긍정적인 영향을 미친다.",
        "10. 전반적으로 AI 기술은 미래 교육 발전에 핵심적인 역할을 할 것이다."
    ]
    options = ["1 (전혀 아니다)", "2 (아니다)", "3 (보통이다)", "4 (그렇다)", "5 (매우 그렇다)"]

    with tab1:
        st.subheader("설문에 참여해 주세요.")
        with st.form("survey_form"):
            user_id_survey = st.text_input("사용자 ID", value=st.session_state["user_id"], disabled=True)
            responses = []
            for q in questions:
                ans = st.radio(q, options, horizontal=True)
                responses.append(int(ans[0]))
            submit_button = st.form_submit_button(label="설문 제출", type="primary")
            if submit_button:
                if user_id_survey.strip() == "":
                    st.error("사용자 ID를 입력해 주세요!")
                else:
                    insert_survey_data(
                        user_id_survey,
                        responses[0], responses[1], responses[2], responses[3], responses[4],
                        responses[5], responses[6], responses[7], responses[8], responses[9]
                    )
                    st.success(f"{user_id_survey}님, 설문이 성공적으로 제출되었습니다. 감사합니다!")

    with tab2:
        st.subheader("설문 결과 통계 및 시각화")
        df = fetch_survey_data()
        if df.empty:
            st.info("아직 제출된 설문 데이터가 없습니다.")
        else:
            st.write(f"**총 응답자 수:** {len(df)}명")
            st.divider()
            for i, q in enumerate(questions):
                col_name = f'q{i+1}'
                st.markdown(f"**{q}**")
                avg_score = df[col_name].mean()
                counts = df[col_name].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
                counts.index = ["1점", "2점", "3점", "4점", "5점"]
                st.bar_chart(counts)
                st.caption(f"이 문항의 평균 점수: **{avg_score:.2f} / 5.0**")
                st.divider()
