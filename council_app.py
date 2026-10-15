import os
import json
import base64
import hashlib
import csv
from io import StringIO
from datetime import datetime
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types

# ==================== 1. 기본 경로 및 데이터 저장소 초기화 ====================
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "council_data"
FILES_DIR = DATA_DIR / "uploaded_files"
LOGO_DIR = DATA_DIR / "branding"
TEMPLATES_DIR = DATA_DIR / "templates"

for d in [DATA_DIR, FILES_DIR, LOGO_DIR, TEMPLATES_DIR]:
    d.mkdir(exist_ok=True)

CONFIG_FILE = DATA_DIR / "site_config.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
SAVED_LOGIN_FILE = DATA_DIR / "saved_login.json"
DEPT_ITEMS_FILE = DATA_DIR / "dept_items.json"
MINUTES_FILE = DATA_DIR / "minutes.json"
TEMPLATES_FILE = DATA_DIR / "report_templates.json"
MEETING_DOCS_FILE = DATA_DIR / "monthly_meeting_docs.json"

# 5단계 직급 체계
ROLES = {
    "president": "👑 회장",
    "vice_president": "🦅 부회장",
    "director": "⭐ 부장",
    "deputy": "🎖️ 차장",
    "member": "🌱 부원"
}

ROLE_DESC = {
    "president": "전 부서 열람·관리 + 회장단 전용 지표 + [회장 단독 기밀 조회]",
    "vice_president": "전 부서 열람·관리 + 회장단 전용 지표(임원명단·예산·회의록) 확인",
    "director": "소속 부서 모든 기능 열람·추가·수정·삭제·공유설정 가능 + 타 부서 공유 항목 열람",
    "deputy": "소속 부서 모든 기능 열람·추가·수정·공유설정 가능 (삭제 불가) + 타 부서 공유 항목 열람",
    "member": "소속 부서 및 타 부서 공유 항목 열람 + 코멘트(댓글) 작성 가능"
}

# 7대 핵심 부서 및 세부 모듈 정의
DEPT_MODULES = {
    "집행부": [
        {"key": "exec_checklist", "name": "✅ 체크리스트", "desc": "집행부 핵심 할 일(To-Do), 마감기한, 달성 여부 점검"},
        {"key": "exec_monthly", "name": "📅 월별행사", "desc": "연간/월별 학생회 주요 행사 일정 및 진행 상태 관리"},
        {"key": "exec_archive", "name": "🗂️ 부서별(월별)기획안보관함", "desc": "각 부서별·월별 제출 기획안/보고서 통합 보관 및 회의자료 연동"}
    ],
    "기획부": [
        {"key": "plan_proposal", "name": "📋 행사기획안", "desc": "신규 행사 기획안 작성 및 AI 큐시트·타임테이블 자동 설계"},
        {"key": "plan_past", "name": "📦 지난 행사 자료함", "desc": "역대 행사 결과보고서, 피드백, 타임테이블 자료 아카이브"}
    ],
    "운영부": [
        {"key": "ops_inventory", "name": "📦 운영창고물품", "desc": "창고 보관 물품 수량, 보관 위치, 대여/점검 상태 관리"},
        {"key": "ops_purchase", "name": "🛒 구매필요항목", "desc": "행사 및 운영에 필요한 물품 구매 요청, 예상 단가·수량 관리"}
    ],
    "총무부": [
        {"key": "fin_audit", "name": "🧾 감사대비(증빙·영수증 보관함)", "desc": "영수증 사진/PDF, 결제 전표, 증빙 서류 업로드 및 감사 대비"},
        {"key": "fin_monthly", "name": "💰 월별결산안", "desc": "수입·지출 내역 장부 기록, 월별 결산표 및 AI 결산 공고문 생성"},
        {"key": "fin_handover", "name": "📘 인수인계사항", "desc": "통장·카드·회계 규정·감사 노하우 등 차기 총무 인수인계서"}
    ],
    "복지부": [
        {"key": "wel_items", "name": "🎁 복지물품관리현황", "desc": "우산·충전기·상비약·공학계산기 등 학우 대여/복지 물품 재고 현황"},
        {"key": "wel_tasks", "name": "🤝 복지업무현황", "desc": "간식사업, 사물함 배정, 제휴 혜택 등 복지 사업 진행 현황"}
    ],
    "홍보부": [
        {"key": "pr_archive", "name": "🎨 홍보물보관함", "desc": "카드뉴스·포스터·현수막 원본 보관 및 AI 홍보문 생성"}
    ],
    "자율(자유전공)부": [
        {"key": "free_news", "name": "🏫 학교(부) 소식", "desc": "학교 본부 및 학부 주요 공지, 학사 일정, 전공 탐색 소식 정리"},
        {"key": "free_support", "name": "🛠️ 보조업무현황", "desc": "타 부서 협업 지원, 행사 현장 서포트, 특화 보조 업무 기록"}
    ]
}

MONTH_OPTIONS = ["상시/전체"] + [f"{m}월" for m in range(1, 13)]

# 실버 그라데이션 2종이 추가된 테마 프리셋
THEME_PRESETS = {
    "platinum_silver": {
        "name": "🪙 플래티넘 실버 그라데이션 (고급 메탈릭 실버·다크크롬)",
        "bg": "linear-gradient(145deg, #11141a 0%, #262c36 42%, #475263 78%, #1e242d 100%)",
        "sidebar": "linear-gradient(180deg, #12151c 0%, #222834 100%)",
        "primary": "#e2e8f0",
        "accent": "#94a3b8"
    },
    "titanium_silver": {
        "name": "🥈 티타늄 아이스 실버 그라데이션 (세련된 브러시드 실버)",
        "bg": "linear-gradient(145deg, #1a202c 0%, #334155 48%, #64748b 85%, #1e293b 100%)",
        "sidebar": "linear-gradient(180deg, #161c26 0%, #283344 100%)",
        "primary": "#f8fafc",
        "accent": "#38bdf8"
    },
    "modern_navy": {
        "name": "🏛️ 모던 네이비 (공식 스탠다드)",
        "bg": "linear-gradient(155deg, #070d19 0%, #0f172a 55%, #1e293b 100%)",
        "sidebar": "linear-gradient(180deg, #091122 0%, #111c35 100%)",
        "primary": "#38bdf8",
        "accent": "#818cf8"
    },
    "royal_crimson": {
        "name": "🦁 로얄 크림슨 (품격 있는 크림슨&골드)",
        "bg": "linear-gradient(155deg, #16070b 0%, #2a0a14 55%, #1f1224 100%)",
        "sidebar": "linear-gradient(180deg, #1a060d 0%, #2d0b16 100%)",
        "primary": "#fb7185",
        "accent": "#fbbf24"
    },
    "emerald_campus": {
        "name": "🌿 에메랄드 캠퍼스 (산뜻한 그린)",
        "bg": "linear-gradient(155deg, #04130e 0%, #06241b 55%, #0f2926 100%)",
        "sidebar": "linear-gradient(180deg, #051812 0%, #092c22 100%)",
        "primary": "#34d399",
        "accent": "#38bdf8"
    },
    "cyber_violet": {
        "name": "⚡ 사이버 바이올렛 (트렌디 네온)",
        "bg": "linear-gradient(155deg, #0d061a 0%, #1a0b2e 55%, #111827 100%)",
        "sidebar": "linear-gradient(180deg, #100720 0%, #1f0e3a 100%)",
        "primary": "#c084fc",
        "accent": "#22d3ee"
    }
}


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def make_session_token(uid: str, pw_hash: str) -> str:
    return hashlib.sha256(f"council_session_{uid}_{pw_hash}".encode("utf-8")).hexdigest()[:24]


def load_site_config() -> dict:
    default_cfg = {
        "year": "2027",
        "generation": "제39대",
        "council_name": "아르곤(ARGON) 학생회",
        "slogan": "학우와 함께 호흡하고 내일로 도약하는 학생회",
        "logo_emoji": "🏛️",
        "logo_file": "",
        "watermark_opacity": 0.06,
        "theme_key": "platinum_silver",
        "use_custom_bg": False,
        "custom_bg_color1": "#11141a",
        "custom_bg_color2": "#2b323f",
        "custom_bg_color3": "#475263",
        "custom_sidebar_color": "#141820",
        "use_custom_color": False,
        "custom_primary": "#e2e8f0",
        "shared_api_key": "",
        "default_model": "gemini-2.5-flash",
        "available_models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
        "departments": list(DEPT_MODULES.keys())
    }
    data = load_json(CONFIG_FILE, default_cfg)
    for k, v in default_cfg.items():
        data.setdefault(k, v)
    if "회장단" in data["departments"]:
        data["departments"] = [d for d in data["departments"] if d != "회장단"]
    for d in DEPT_MODULES.keys():
        if d not in data["departments"]:
            data["departments"].append(d)
    return data


def load_and_fix_accounts() -> dict:
    accs = load_json(ACCOUNTS_FILE, {})
    changed = False
    role_migration = {
        "admin": "president",
        "lead": "director",
        "member": "member"
    }
    has_president = False
    for idx, (uid_k, info) in enumerate(accs.items()):
        r = info.get("role", "member")
        if r in role_migration and r != role_migration[r]:
            info["role"] = role_migration[r]
            changed = True
        if info.get("role") not in ROLES:
            info["role"] = "president" if idx == 0 else "member"
            changed = True
        if info.get("dept") in ["회장단", "", None] or info.get("dept") not in DEPT_MODULES:
            info["dept"] = "집행부"
            changed = True
        if info.get("role") == "president":
            has_president = True

    if accs and not has_president:
        first_key = next(iter(accs.keys()))
        accs[first_key]["role"] = "president"
        changed = True

    if changed:
        save_json(ACCOUNTS_FILE, accs)
    return accs


def load_templates() -> list:
    default_tpls = [
        {
            "id": "tpl_plan_std",
            "name": "📋 표준 월별 사업/행사 기획안 양식 (기본 제공)",
            "type": "기획안",
            "content": """### 1. 사업 개요
- **사업/행사명**: 
- **주관 부서 / 담당자**: 
- **일시 및 장소**: 
- **참여 대상 및 예상 인원**: 

### 2. 기획 의도 및 목적
- 

### 3. 세부 진행 계획 (타임테이블)
| 시간 | 진행 내용 | 담당자 | 비고(준비물) |
| :--- | :--- | :--- | :--- |
| 13:00 ~ 14:00 | 사전 세팅 및 리허설 | 전원 | 현수막, 음향 점검 |

### 4. 소요 예산안
| 항목 | 산출 내역 | 금액(원) | 비고 |
| :--- | :--- | :--- | :--- |
| 물품 구매비 | 상세 내역 기재 | 0원 | 영수증 첨부 예정 |

### 5. 타 부서 협조 요청 사항 (회의 안건)
- **홍보부**: 카드뉴스 제작 및 공지방 홍보 요청일 ( / )
- **운영부/총무부**: 물품 및 예산 집행 협조 사항""",
            "file": ""
        },
        {
            "id": "tpl_report_std",
            "name": "📊 표준 월별 업무/행사 결과보고서 양식 (기본 제공)",
            "type": "결과보고서",
            "content": """### 1. 이달의 부서 핵심 업무 요약
- **보고 부서**: 
- **보고 대상 월**: 
- **완료 업무 건수**: 

### 2. 주요 진행 성과 및 결산 요약
- **잘된 점 (Keep)**: 
- **아쉬운 점 및 개선사항 (Problem & Try)**: 
- **예산 집행 내역**: 총 지출 0원 (잔여 0원)

### 3. 다음 달 예정 업무 및 정기회의 건의 안건
- """,
            "file": ""
        }
    ]
    return load_json(TEMPLATES_FILE, default_tpls)


def get_logo_data_uri(cfg: dict) -> str:
    logo_rel = cfg.get("logo_file", "")
    if logo_rel:
        lpath = LOGO_DIR / logo_rel
        if lpath.exists():
            ext = lpath.suffix.lower().lstrip(".")
            mime = {
                "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "webp": "image/webp", "svg": "image/svg+xml", "gif": "image/gif"
            }.get(ext, "image/png")
            b64 = base64.b64encode(lpath.read_bytes()).decode("utf-8")
            return f"data:{mime};base64,{b64}"
    return ""


# ==================== 2. 페이지 설정 & 커스텀 그라데이션/로고 CSS ====================
cfg = load_site_config()
logo_uri = get_logo_data_uri(cfg)

st.set_page_config(
    page_title=f"{cfg['year']} {cfg['generation']} {cfg['council_name']}",
    page_icon=cfg.get("logo_emoji", "🏛️"),
    layout="wide",
    initial_sidebar_state="expanded"
)


def render_html(html_str: str):
    cleaned = "\n".join(line.strip() for line in html_str.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


theme = THEME_PRESETS.get(cfg.get("theme_key", "platinum_silver"), THEME_PRESETS["platinum_silver"])

# 배경 그라데이션 직접 지정 여부 확인
if cfg.get("use_custom_bg"):
    c1 = cfg.get("custom_bg_color1", "#11141a")
    c2 = cfg.get("custom_bg_color2", "#2b323f")
    c3 = cfg.get("custom_bg_color3", "#475263")
    sb_c = cfg.get("custom_sidebar_color", "#141820")
    bg_css_val = f"linear-gradient(145deg, {c1} 0%, {c2} 50%, {c3} 100%)"
    sidebar_css_val = f"linear-gradient(180deg, {sb_c} 0%, {c1} 100%)"
else:
    bg_css_val = theme["bg"]
    sidebar_css_val = theme["sidebar"]

p_color = cfg["custom_primary"] if cfg.get("use_custom_color") else theme["primary"]
wm_opacity = float(cfg.get("watermark_opacity", 0.06))

bg_watermark_css = ""
if logo_uri:
    bg_watermark_css = f"""
    .stApp::before {{
        content: "";
        position: fixed;
        top: 52%;
        left: 56%;
        transform: translate(-50%, -50%);
        width: 520px;
        height: 520px;
        background-image: url('{logo_uri}');
        background-repeat: no-repeat;
        background-position: center;
        background-size: contain;
        opacity: {wm_opacity};
        pointer-events: none;
        z-index: 0;
        filter: drop-shadow(0 0 30px {p_color}55);
    }}
    """

render_html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
html, body, [class*="css"] {{ font-family: 'Noto Sans KR', sans-serif; }}
.stApp {{ background: {bg_css_val}; color: #f1f5f9; }}
{bg_watermark_css}
[data-testid="stSidebar"] {{ background: {sidebar_css_val}; border-right: 1px solid {p_color}33; }}
.council-banner {{
    position: relative; overflow: hidden;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(38, 46, 62, 0.78) 100%);
    border: 1px solid {p_color}66; border-left: 6px solid {p_color};
    border-radius: 16px; padding: 20px 26px; margin-bottom: 18px;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.45); backdrop-filter: blur(12px);
}}
.banner-watermark {{
    position: absolute; right: -15px; top: -25px; width: 190px; height: 190px;
    object-fit: contain; opacity: 0.11; pointer-events: none;
    transform: rotate(-8deg); filter: blur(0.4px) drop-shadow(0 0 12px {p_color});
}}
.logo-frame {{
    width: 64px; height: 64px; border-radius: 16px;
    background: radial-gradient(circle, rgba(255,255,255,0.16) 0%, rgba(15,23,42,0.85) 100%);
    border: 1.5px solid {p_color}99; box-shadow: 0 0 18px {p_color}44;
    display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0;
}}
.logo-frame img {{ width: 86%; height: 86%; object-fit: contain; }}
.logo-mini {{
    width: 34px; height: 34px; border-radius: 9px;
    border: 1px solid {p_color}77; background: rgba(15,23,42,0.8);
    object-fit: contain; padding: 3px;
}}
.council-title {{ font-size: 1.6rem; font-weight: 900; color: #f8fafc; letter-spacing: -0.3px; }}
.council-sub {{ font-size: 0.9rem; color: #cbd5e1; margin-top: 3px; }}
.stat-card {{
    background: rgba(15, 23, 42, 0.84); border: 1px solid {p_color}44;
    border-radius: 12px; padding: 11px 16px; text-align: center; backdrop-filter: blur(6px);
}}
.stat-val {{ font-size: 1.2rem; font-weight: 900; color: {p_color}; }}
.stat-lbl {{ font-size: 0.75rem; color: #94a3b8; }}
.role-badge {{
    display: inline-block; background: {p_color}28; border: 1px solid {p_color};
    color: #f8fafc; font-size: 0.75rem; font-weight: 700; padding: 2px 10px; border-radius: 999px;
}}
.share-badge-on {{
    display: inline-block; background: rgba(52, 211, 153, 0.18); border: 1px solid #34d399;
    color: #6ee7b7; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 999px;
}}
.share-badge-off {{
    display: inline-block; background: rgba(248, 113, 113, 0.18); border: 1px solid #f87171;
    color: #fca5a5; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 999px;
}}

.dept-card {{
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.90) 0%, rgba(30, 41, 59, 0.82) 100%);
    border: 1.5px solid rgba(148, 163, 184, 0.28);
    border-top: 4px solid var(--card-accent, #38bdf8);
    border-radius: 16px;
    padding: 20px 20px 14px 20px;
    margin-bottom: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    transition: all 0.2s ease-in-out;
    min-height: 158px;
}}
.dept-card-my {{
    border: 1.8px solid var(--card-accent, #38bdf8);
    border-top: 5px solid var(--card-accent, #38bdf8);
    box-shadow: 0 0 22px rgba(56, 189, 248, 0.22);
}}
.dept-card-title {{
    font-size: 1.25rem;
    font-weight: 900;
    color: #f8fafc;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.dept-card-desc {{
    font-size: 0.83rem;
    color: #cbd5e1;
    margin-bottom: 12px;
    line-height: 1.45;
}}
.mod-pill {{
    display: inline-block;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #e2e8f0;
    font-size: 0.74rem;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 8px;
    margin-right: 5px;
    margin-bottom: 5px;
}}
</style>

""")


# ==================== 3. 권한(RBAC) 판별 함수 ====================
def is_presidency(role: str) -> bool:
    return role in ["president", "vice_president"]


def can_view_budget_balance(role: str, dept: str) -> bool:
    return is_presidency(role) or (dept == "총무부")


def can_view_item(role: str, user_dept: str, target_dept: str, item_is_shared: bool) -> bool:
    if is_presidency(role) or (user_dept == target_dept):
        return True
    return bool(item_is_shared)


def can_create_or_edit(role: str, user_dept: str, target_dept: str) -> bool:
    if is_presidency(role):
        return True
    return (role in ["director", "deputy"]) and (user_dept == target_dept)


def can_delete_item(role: str, user_dept: str, target_dept: str) -> bool:
    if is_presidency(role):
        return True
    return (role == "director") and (user_dept == target_dept)


# ==================== 4. 새로고침(F5) 시에도 풀리지 않는 영구 로그인 세션 복원 ====================
accounts = load_and_fix_accounts()
saved_login_info = load_json(SAVED_LOGIN_FILE, {"saved_id": "", "remember": True, "auto_login_user": ""})

if "council_user" not in st.session_state:
    st.session_state.council_user = None

# 1순위: URL 쿼리 파라미터(uid, token)로 새로고침 시 로그인 즉시 복원
if not st.session_state.council_user:
    q_uid = st.query_params.get("uid", "")
    q_tok = st.query_params.get("token", "")
    if q_uid and q_uid in accounts:
        expected_tok = make_session_token(q_uid, accounts[q_uid].get("pw_hash", ""))
        if q_tok == expected_tok:
            st.session_state.council_user = q_uid

# 2순위: 로컬 설정 파일(auto_login_user)로 새로고침/재접속 시 자동 복원
if not st.session_state.council_user:
    auto_u = saved_login_info.get("auto_login_user", "")
    if auto_u and auto_u in accounts:
        st.session_state.council_user = auto_u
        st.query_params["uid"] = auto_u
        st.query_params["token"] = make_session_token(auto_u, accounts[auto_u].get("pw_hash", ""))

logo_box_html = (
    f'<div class="logo-frame"><img src="{logo_uri}" alt="logo"/></div>'
    if logo_uri else
    f'<div class="logo-frame"><span style="font-size:2.0rem;">{cfg.get("logo_emoji", "🏛️")}</span></div>'
)
watermark_img_html = f'<img src="{logo_uri}" class="banner-watermark" alt="wm"/>' if logo_uri else ""

if not st.session_state.council_user:
    render_html(f"""
    <div class="council-banner">
        {watermark_img_html}
        <div style="display:flex; align-items:center; justify-content:center; gap:16px;">
            {logo_box_html}
            <div style="text-align:left;">
                <div class="council-title">{cfg['year']}학년도 {cfg['generation']} {cfg['council_name']}</div>
                <div class="council-sub">{cfg['slogan']} — 부서별 권한 분리형 통합 워크스페이스</div>
            </div>
        </div>
    </div>
    """)

    c_l, c_m, c_r = st.columns([1, 1.35, 1])
    with c_m:
        if not accounts:
            st.info("👋 **최초 실행 안내:** 아직 등록된 임원 계정이 없습니다. 첫 번째로 가입하는 계정은 자동으로 **👑 회장 (집행부)** 권한이 부여됩니다!")

        tab_login, tab_reg = st.tabs(["🔐 임원진 로그인", "✨ 신규 임원 계정 등록"])

        with tab_login:
            default_id = saved_login_info.get("saved_id", "") if saved_login_info.get("remember", True) else ""
            lid = st.text_input("아이디 (ID)", value=default_id, key="l_id")
            lpw = st.text_input("비밀번호 (Password)", type="password", key="l_pw")
            col_chk1, col_chk2 = st.columns(2)
            rem_id = col_chk1.checkbox("☑️ 아이디 저장", value=bool(saved_login_info.get("remember", True)))
            keep_login = col_chk2.checkbox("🔒 새로고침 시에도 로그인 유지", value=True)

            if st.button("🚀 워크스페이스 로그인", type="primary", use_container_width=True):
                uid = lid.strip()
                if uid in accounts and accounts[uid].get("pw_hash") == hash_pw(lpw):
                    if not accounts[uid].get("pw_plain"):
                        accounts[uid]["pw_plain"] = lpw
                        save_json(ACCOUNTS_FILE, accounts)
                    save_json(SAVED_LOGIN_FILE, {
                        "saved_id": uid if rem_id else "",
                        "remember": bool(rem_id),
                        "auto_login_user": uid if keep_login else ""
                    })
                    st.session_state.council_user = uid
                    st.query_params["uid"] = uid
                    st.query_params["token"] = make_session_token(uid, accounts[uid]["pw_hash"])
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")

        with tab_reg:
            rid = st.text_input("사용할 아이디 (ID)", placeholder="예: president2027", key="r_id")
            rpw = st.text_input("사용할 비밀번호 (Password)", type="password", key="r_pw")
            rname = st.text_input("이름", placeholder="예: 홍길동", key="r_name")
            rdept = st.selectbox("소속 부서 (회장·부회장은 집행부 선택)", cfg["departments"], index=0, key="r_dept")

            is_first_user = (len(accounts) == 0)
            if is_first_user:
                assigned_role = "president"
                st.success("👑 첫 번째 가입자이므로 자동으로 **[👑 회장]** 직급이 부여됩니다.")
            else:
                assigned_role = st.selectbox(
                    "신청 직급 (가입 후 회장단이 변경 가능)",
                    options=["member", "deputy", "director", "vice_president"],
                    format_func=lambda k: ROLES[k],
                    key="r_role"
                )

            if st.button("✨ 계정 생성 및 바로 시작", type="primary", use_container_width=True):
                uid = rid.strip()
                if not uid or not rpw or not rname.strip():
                    st.warning("아이디, 비밀번호, 이름을 모두 입력해주세요.")
                elif uid in accounts:
                    st.error("이미 존재하는 아이디입니다.")
                else:
                    pw_h = hash_pw(rpw)
                    accounts[uid] = {
                        "pw_hash": pw_h,
                        "pw_plain": rpw,
                        "name": rname.strip(),
                        "dept": rdept,
                        "role": assigned_role,
                        "api_key": "",
                        "joined_at": datetime.now().strftime("%Y-%m-%d")
                    }
                    save_json(ACCOUNTS_FILE, accounts)
                    save_json(SAVED_LOGIN_FILE, {"saved_id": uid, "remember": True, "auto_login_user": uid})
                    st.session_state.council_user = uid
                    st.query_params["uid"] = uid
                    st.query_params["token"] = make_session_token(uid, pw_h)
                    st.rerun()
    st.stop()


# ==================== 5. 로그인 후 사용자 정보 및 사이드바 ====================
uid = st.session_state.council_user
user_info = accounts.get(uid, {})
user_role = user_info.get("role", "member")
user_dept = user_info.get("dept", "집행부")
user_name = user_info.get("name", uid)
active_api_key = user_info.get("api_key") or cfg.get("shared_api_key", "")
selected_model = cfg.get("default_model", "gemini-2.5-flash")

mini_logo_html = (
    f'<img src="{logo_uri}" class="logo-mini" alt="logo"/>'
    if logo_uri else
    f'<span style="font-size:1.3rem;">{cfg.get("logo_emoji", "🏛️")}</span>'
)

with st.sidebar:
    render_html(f"""
    <div class="stat-card" style="text-align:left; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
                {mini_logo_html}
                <span style="font-size:1.05rem; font-weight:900; color:#f8fafc;">{user_name}</span>
            </div>
            <span class="role-badge">{ROLES.get(user_role, '🌱 부원')}</span>
        </div>
        <div style="font-size:0.8rem; color:{p_color}; font-weight:700; margin-top:8px;">소속 부서: {user_dept}</div>
        <div style="font-size:0.72rem; color:#94a3b8; margin-top:4px;">{ROLE_DESC.get(user_role, '')}</div>
    </div>
    """)

    if st.button("🚪 로그아웃 (계정 전환)", use_container_width=True):
        st.session_state.council_user = None
        st.query_params.clear()
        saved_login_info["auto_login_user"] = ""
        save_json(SAVED_LOGIN_FILE, saved_login_info)
        st.rerun()

    first_acc_id = next(iter(accounts.keys())) if accounts else ""
    if uid == first_acc_id and user_role != "president":
        if st.button("👑 내 계정 회장(President) 권한 즉시 복구", type="primary", use_container_width=True):
            accounts[uid]["role"] = "president"
            accounts[uid]["dept"] = "집행부"
            save_json(ACCOUNTS_FILE, accounts)
            st.rerun()

    if "active_page" not in st.session_state:
        st.session_state.active_page = "HOME"
    if "active_sub_idx" not in st.session_state:
        st.session_state.active_sub_idx = 0

    st.divider()
    st.markdown("##### 🧭 워크스페이스 빠른 이동")
    if st.button("🏠 전체 부서 홈 화면 (메인 런처)", type="primary" if st.session_state.active_page == "HOME" else "secondary", use_container_width=True):
        st.session_state.active_page = "HOME"
        st.session_state.active_sub_idx = 0
        st.rerun()

    dept_icons = {
        "집행부": "⚡", "기획부": "📋", "운영부": "📦", "총무부": "💰",
        "복지부": "🎁", "홍보부": "📢", "자율(자유전공)부": "🏫"
    }
    sb_c1, sb_c2 = st.columns(2)
    for d_i, d_k in enumerate(["집행부", "기획부", "운영부", "총무부", "복지부", "홍보부", "자율(자유전공)부"]):
        target_col = sb_c1 if d_i % 2 == 0 else sb_c2
        short_lbl = "자율부" if "자율" in d_k else d_k
        is_cur = (st.session_state.active_page == d_k)
        if target_col.button(f"{dept_icons.get(d_k, '🏛️')} {short_lbl}", key=f"sb_nav_{d_k}", type="primary" if is_cur else "secondary", use_container_width=True):
            st.session_state.active_page = d_k
            st.session_state.active_sub_idx = 0
            st.rerun()

    if st.button("📑 월별 통합 회의자료 & 회의록", type="primary" if st.session_state.active_page == "MEETING_HUB" else "secondary", use_container_width=True):
        st.session_state.active_page = "MEETING_HUB"
        st.session_state.active_sub_idx = 0
        st.rerun()

    if st.button("👑 관리 · 로고 · 디자인 설정", type="primary" if st.session_state.active_page == "ADMIN_SETTINGS" else "secondary", use_container_width=True):
        st.session_state.active_page = "ADMIN_SETTINGS"
        st.session_state.active_sub_idx = 0
        st.rerun()

    st.divider()
    st.caption(f"📅 **오늘 날짜:** {datetime.now().strftime('%Y년 %m월 %d일')}")
    st.caption(f"🏛️ **{cfg['year']} {cfg['generation']} {cfg['council_name']}**")


def call_ai(system_prompt: str, user_prompt: str, temp: float = 0.35) -> str:
    if not active_api_key:
        raise ValueError("[👑 9. 관리·디자인 설정] 탭 하단의 숨김 메뉴(🔧 AI 엔진 & API 키 설정)에서 API Key를 먼저 등록해주세요!")
    cl = genai.Client(api_key=active_api_key)
    resp = cl.models.generate_content(
        model=selected_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temp
        )
    )
    return resp.text


# ==================== 6. 데이터 로드 및 보안형 상단 대시보드 헤더 ====================
dept_items = load_json(DEPT_ITEMS_FILE, {})
minutes_data = load_json(MINUTES_FILE, [])
templates_data = load_templates()
meeting_docs_data = load_json(MEETING_DOCS_FILE, [])

fin_entries = dept_items.get("총무부", {}).get("fin_monthly", [])
total_income = sum(int(x.get("extra", {}).get("amount", 0)) for x in fin_entries if x.get("extra", {}).get("tx_type") == "수입")
total_expense = sum(int(x.get("extra", {}).get("amount", 0)) for x in fin_entries if x.get("extra", {}).get("tx_type") == "지출")
current_balance = total_income - total_expense

stat_cards_html = f'<div class="stat-card"><div class="stat-val">{user_dept}</div><div class="stat-lbl">내 소속 부서</div></div>'
stat_cards_html += f'<div class="stat-card"><div class="stat-val">{ROLES.get(user_role, "")}</div><div class="stat-lbl">내 직급</div></div>'

if can_view_budget_balance(user_role, user_dept):
    stat_cards_html += f'<div class="stat-card"><div class="stat-val">{current_balance:,}원</div><div class="stat-lbl">🔒 학생회비 잔액</div></div>'

if is_presidency(user_role):
    stat_cards_html += f'<div class="stat-card"><div class="stat-val">{len(accounts)}명</div><div class="stat-lbl">🔒 등록 임원진</div></div>'
    stat_cards_html += f'<div class="stat-card"><div class="stat-val">{len(minutes_data)}건</div><div class="stat-lbl">🔒 누적 회의록</div></div>'

render_html(f"""
<div class="council-banner">
    {watermark_img_html}
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; position:relative; z-index:1;">
        <div style="display:flex; align-items:center; gap:16px;">
            {logo_box_html}
            <div>
                <div class="council-title">{cfg['year']}학년도 {cfg['generation']} {cfg['council_name']}</div>
                <div class="council-sub">{cfg['slogan']}</div>
            </div>
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
            {stat_cards_html}
        </div>
    </div>
</div>
""")


# ==================== 7. 공통 모듈 아이템 렌더링 & 월별 회의자료 연동 함수 ====================
def render_module_board(dept_name: str, mod_info: dict):
    mod_key = mod_info["key"]
    mod_name = mod_info["name"]
    mod_desc = mod_info["desc"]

    dept_items.setdefault(dept_name, {})
    dept_items[dept_name].setdefault(mod_key, [])
    items = dept_items[dept_name][mod_key]

    has_write = can_create_or_edit(user_role, user_dept, dept_name)
    has_delete = can_delete_item(user_role, user_dept, dept_name)

    perm_msg = []
    if is_presidency(user_role):
        perm_msg.append("👑 **회장·부회장 권한**: 모든 항목 열람·추가·수정·삭제 가능")
    elif user_dept == dept_name:
        if user_role == "director":
            perm_msg.append(f"⭐ **{dept_name} 부장 권한**: 모든 항목 열람·추가·수정·삭제·공유설정 가능")
        elif user_role == "deputy":
            perm_msg.append(f"🎖️ **{dept_name} 차장 권한**: 모든 항목 열람·추가·수정·공유설정 가능 *(삭제 불가)*")
        else:
            perm_msg.append(f"🌱 **{dept_name} 부원 권한**: 부서 내 모든 항목 열람 및 코멘트 작성 가능 *(추가·수정·삭제 불가)*")
    else:
        perm_msg.append(f"🔍 **타 부서({user_dept}) 열람 모드**: `{dept_name}`에서 **[🔓 타 부서 공유 허용]**으로 설정한 항목만 열람 및 코멘트 작성 가능")

    st.caption(f"{mod_desc}  |  " + " ".join(perm_msg))

    if mod_key == "exec_archive":
        st.info("💡 각 부서에서 작성 시 **'📑 월별 정기회의 자료에 포함'**을 체크한 모든 기획안·보고서가 이곳과 **[📑 8. 월별 통합 회의자료 & 회의록]** 탭에 자동으로 취합됩니다.")

    if mod_key == "fin_monthly":
        if can_view_budget_balance(user_role, user_dept):
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("➕ 총무부 누적 수입", f"{total_income:,} 원")
            fc2.metric("➖ 총무부 누적 지출", f"{total_expense:,} 원")
            fc3.metric("🏦 현재 학생회비 잔액 (회장·부회장·총무 전용)", f"{current_balance:,} 원")
            if items:
                csv_buf = StringIO()
                writer = csv.writer(csv_buf)
                writer.writerow(["날짜", "대상월", "구분", "항목명", "금액(원)", "세부내용/증빙", "작성자", "타부서공유"])
                for it in items:
                    ex = it.get("extra", {})
                    writer.writerow([
                        it.get("created_at", ""),
                        it.get("target_month", "상시/전체"),
                        ex.get("tx_type", ""),
                        it.get("title", ""),
                        ex.get("amount", 0),
                        it.get("content", ""),
                        it.get("author", ""),
                        "O" if it.get("is_shared") else "X"
                    ])
                st.download_button(
                    "📊 월별결산 장부 엑셀(CSV) 다운로드",
                    data=csv_buf.getvalue().encode("utf-8-sig"),
                    file_name=f"{cfg['year']}_{dept_name}_월별결산장부.csv",
                    mime="text/csv",
                    key=f"csv_{mod_key}"
                )
        else:
            st.info("🔒 실시간 학생회비 총잔액 현황은 보안상 **회장·부회장 및 총무부**에만 표시됩니다. 아래에서 공유 허용된 월별 결산안을 열람하실 수 있습니다.")

    if has_write:
        with st.expander(f"➕ [{mod_name}] 새 항목 / 월별 기획안·보고서 등록", expanded=False):
            tpl_names = ["(양식 미선택 - 자유 작성)"] + [t["name"] for t in templates_data]
            sel_tpl_name = st.selectbox("📄 표준 기획안/보고서 양식 불러오기 (선택 시 아래 본문에 양식이 자동 적용됨)", tpl_names, key=f"tpl_sel_{dept_name}_{mod_key}")
            default_body = ""
            if sel_tpl_name != "(양식 미선택 - 자유 작성)":
                for t in templates_data:
                    if t["name"] == sel_tpl_name:
                        default_body = t.get("content", "")
                        break

            with st.form(key=f"form_add_{dept_name}_{mod_key}", clear_on_submit=True):
                f_c1, f_c2, f_c3 = st.columns([2.2, 1, 1.1])
                with f_c1:
                    title = st.text_input("제목 / 항목명", placeholder=f"예: [3월] {dept_name} 신입생 환영회 기획안 / 결과보고서")
                with f_c2:
                    cur_m_str = f"{datetime.now().month}월"
                    m_idx = MONTH_OPTIONS.index(cur_m_str) if cur_m_str in MONTH_OPTIONS else 0
                    target_month = st.selectbox("📅 해당 월 (@월 분류)", MONTH_OPTIONS, index=m_idx)
                with f_c3:
                    is_shared = st.checkbox("🔓 타 부서 열람 공유", value=True)
                    include_meeting = st.checkbox("📑 월별 회의자료에 통합", value=True)

                extra_data = {}
                if mod_key == "exec_checklist":
                    ec1, ec2, ec3 = st.columns(3)
                    extra_data["due_date"] = ec1.text_input("마감 기한", placeholder="예: 2027-03-25")
                    extra_data["assignee"] = ec2.text_input("담당자/담당부서", placeholder="예: 기획부 부장")
                    extra_data["done"] = ec3.selectbox("진행 상태", ["⏳ 진행중", "✅ 완료", "🚨 긴급점검"])
                elif mod_key == "exec_monthly":
                    extra_data["event_date"] = st.text_input("세부 일시/장소", placeholder="예: 3월 28일 대강당")
                elif mod_key == "exec_archive":
                    extra_data["origin_dept"] = st.selectbox("제출 부서 선택", cfg["departments"])
                elif mod_key in ["ops_inventory", "wel_items"]:
                    ic1, ic2, ic3 = st.columns(3)
                    extra_data["qty"] = ic1.number_input("현재 수량(개)", min_value=0, value=1, step=1)
                    extra_data["location"] = ic2.text_input("보관 위치 / 대여처", placeholder="예: 학생회실 A선반")
                    extra_data["status"] = ic3.selectbox("물품 상태", ["🟢 정상/충분", "🟡 보충필요", "🔴 수리/폐기요망", "📦 대여중"])
                elif mod_key == "ops_purchase":
                    pc1, pc2, pc3 = st.columns(3)
                    extra_data["req_qty"] = pc1.number_input("필요 수량", min_value=1, value=1)
                    extra_data["est_price"] = pc2.number_input("예상 총액(원)", min_value=0, value=10000, step=1000)
                    extra_data["urgency"] = pc3.selectbox("구매 상태", ["🛒 구매요청", "✅ 승인완료", "📦 구매·입고완료"])
                elif mod_key == "fin_monthly":
                    fc1, fc2 = st.columns(2)
                    extra_data["tx_type"] = fc1.selectbox("수입/지출 구분", ["지출", "수입", "월별결산서"])
                    extra_data["amount"] = fc2.number_input("금액(원)", min_value=0, value=0, step=1000)
                elif mod_key == "fin_audit":
                    ac1, ac2 = st.columns(2)
                    extra_data["receipt_no"] = ac1.text_input("영수증/전표 번호", placeholder="예: 카드전표 #2027-0312")
                    extra_data["audit_status"] = ac2.selectbox("증빙 점검 상태", ["✅ 증빙완비", "🟡 영수증추가필요", "🔍 감사검토완료"])

                content = st.text_area("상세 기획안 / 보고서 본문 (마크다운 표 지원)", value=default_body, height=160)
                up_file = st.file_uploader("📎 기획안/보고서/영수증/포스터 파일 첨부 (HWP, DOCX, PDF, XLSX, 이미지 등)", key=f"uf_{dept_name}_{mod_key}")

                submitted = st.form_submit_button("💾 등록 및 저장하기", type="primary", use_container_width=True)
                if submitted:
                    if not title.strip():
                        st.warning("제목/항목명을 입력해주세요.")
                    else:
                        saved_filename = ""
                        if up_file is not None:
                            safe_fn = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{up_file.name}"
                            (FILES_DIR / safe_fn).write_bytes(up_file.getvalue())
                            saved_filename = safe_fn

                        new_item = {
                            "id": f"item_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                            "title": title.strip(),
                            "target_month": target_month,
                            "include_in_meeting": bool(include_meeting),
                            "content": content.strip(),
                            "author": f"{user_name} ({ROLES.get(user_role, '')})",
                            "author_id": uid,
                            "dept": dept_name,
                            "mod_name": mod_name,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "is_shared": bool(is_shared),
                            "extra": extra_data,
                            "attachment": saved_filename,
                            "comments": []
                        }
                        items.insert(0, new_item)
                        save_json(DEPT_ITEMS_FILE, dept_items)
                        st.success("항목이 정상 등록되었습니다!")
                        st.rerun()

            ai_prompt_hint = st.text_input(
                f"🤖 [{mod_name}] AI 초안 자동 생성기 — 키워드만 입력하면 위 양식에 맞춘 초안을 작성해줍니다",
                placeholder="예: 3월 개강총회 기획안 및 타임테이블 짜줘 / 3월 학생회비 결산 보고서 초안 짜줘",
                key=f"ai_hint_{dept_name}_{mod_key}"
            )
            if st.button(f"✨ AI 초안 작성", key=f"ai_btn_{dept_name}_{mod_key}"):
                if ai_prompt_hint.strip():
                    with st.spinner("AI가 초안을 작성 중입니다..."):
                        try:
                            sys_p = f"너는 {cfg['year']}학년도 {cfg['generation']} {cfg['council_name']} [{dept_name}]의 수석 부장이야. [{mod_name}] 업무에 바로 붙여넣을 수 있도록 마크다운 표와 체크리스트를 포함해 작성해."
                            st.markdown(call_ai(sys_p, ai_prompt_hint))
                        except Exception as e:
                            st.error(f"AI 안내: {e}")

    filter_col1, filter_col2 = st.columns([1.2, 3])
    sel_filter_month = filter_col1.selectbox("📅 월별 모아보기 필터", ["전체 보기"] + MONTH_OPTIONS, key=f"flt_m_{dept_name}_{mod_key}")

    visible_items = []
    for idx, it in enumerate(items):
        if not can_view_item(user_role, user_dept, dept_name, it.get("is_shared", True)):
            continue
        if sel_filter_month != "전체 보기" and it.get("target_month", "상시/전체") != sel_filter_month:
            continue
        visible_items.append((idx, it))

    if not visible_items:
        st.info("📭 현재 조건에 해당하는 등록 항목이 없습니다.")
        return

    for orig_idx, it in visible_items:
        item_id = it.get("id", f"{mod_key}_{orig_idx}")
        shared_flag = it.get("is_shared", True)
        mtg_flag = it.get("include_in_meeting", True)
        t_month = it.get("target_month", "상시/전체")
        ex = it.get("extra", {})

        meta_tags = [t_month]
        for k, v in ex.items():
            if v is not None and str(v) != "":
                if k == "amount":
                    if can_view_budget_balance(user_role, user_dept) or shared_flag:
                        meta_tags.append(f"{int(v):,}원")
                else:
                    meta_tags.append(str(v))
        tag_str = f" [{' | '.join(meta_tags)}]" if meta_tags else ""
        share_icon = "🔓공유됨" if shared_flag else "🔒부서전용"
        mtg_icon = "📑회의자료포함" if mtg_flag else ""

        with st.expander(f"📌 {it.get('title')}{tag_str} — ({share_icon} {mtg_icon} | {it.get('author')} | {it.get('created_at')})", expanded=(orig_idx == 0)):
            b1_html = '<span class="share-badge-on">🔓 타 부서 열람 허용</span>' if shared_flag else '<span class="share-badge-off">🔒 우리 부서 & 회장단 전용</span>'
            b2_html = f'<span class="role-badge" style="margin-left:6px;">📅 {t_month} | {"📑 정기회의 자료 포함" if mtg_flag else "일반 보관"}</span>'
            render_html(f"<div style='margin-bottom:8px;'>{b1_html}{b2_html}</div>")

            if it.get("content"):
                st.markdown(it["content"])

            att_name = it.get("attachment", "")
            if att_name:
                att_path = FILES_DIR / att_name
                if att_path.exists():
                    orig_fn = att_name.split("_", 2)[-1]
                    ext = att_path.suffix.lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                        st.image(str(att_path), caption=f"첨부 이미지: {orig_fn}", width=360)
                    st.download_button(
                        f"📥 첨부파일 다운로드 ({orig_fn})",
                        data=att_path.read_bytes(),
                        file_name=orig_fn,
                        key=f"dl_{item_id}"
                    )

            if has_write:
                with st.popover("✏️ 항목 내용 / 해당 월 / 회의자료 포함 여부 수정"):
                    new_t = st.text_input("제목 수정", value=it.get("title", ""), key=f"et_{item_id}")
                    new_m = st.selectbox("📅 해당 월 변경", MONTH_OPTIONS, index=MONTH_OPTIONS.index(t_month) if t_month in MONTH_OPTIONS else 0, key=f"em_{item_id}")
                    new_c = st.text_area("내용 수정", value=it.get("content", ""), height=120, key=f"ec_{item_id}")
                    new_sh = st.checkbox("🔓 타 부서 공유 허용", value=bool(shared_flag), key=f"esh_{item_id}")
                    new_mtg = st.checkbox("📑 월별 정기회의 통합자료에 포함", value=bool(mtg_flag), key=f"emtg_{item_id}")

                    if "done" in ex:
                        opts = ["⏳ 진행중", "✅ 완료", "🚨 긴급점검"]
                        ex["done"] = st.selectbox("진행 상태 변경", opts, index=opts.index(ex["done"]) if ex["done"] in opts else 0, key=f"edone_{item_id}")
                    if "qty" in ex:
                        ex["qty"] = st.number_input("현재 수량 변경", min_value=0, value=int(ex["qty"]), key=f"eqty_{item_id}")
                    if "status" in ex:
                        s_opts = ["🟢 정상/충분", "🟡 보충필요", "🔴 수리/폐기요망", "📦 대여중"]
                        ex["status"] = st.selectbox("물품 상태 변경", s_opts, index=s_opts.index(ex["status"]) if ex["status"] in s_opts else 0, key=f"ests_{item_id}")
                    if "urgency" in ex:
                        u_opts = ["🛒 구매요청", "✅ 승인완료", "📦 구매·입고완료"]
                        ex["urgency"] = st.selectbox("구매 상태 변경", u_opts, index=u_opts.index(ex["urgency"]) if ex["urgency"] in u_opts else 0, key=f"eurg_{item_id}")

                    if st.button("💾 수정사항 저장", type="primary", key=f"esave_{item_id}", use_container_width=True):
                        items[orig_idx]["title"] = new_t.strip()
                        items[orig_idx]["target_month"] = new_m
                        items[orig_idx]["content"] = new_c.strip()
                        items[orig_idx]["is_shared"] = bool(new_sh)
                        items[orig_idx]["include_in_meeting"] = bool(new_mtg)
                        items[orig_idx]["extra"] = ex
                        save_json(DEPT_ITEMS_FILE, dept_items)
                        st.success("수정되었습니다!")
                        st.rerun()

            if has_delete:
                if st.button("🗑️ 이 항목 삭제 (회장·부회장·부장 전용)", key=f"del_{item_id}"):
                    items.pop(orig_idx)
                    save_json(DEPT_ITEMS_FILE, dept_items)
                    st.rerun()
            elif user_role == "deputy" and user_dept == dept_name:
                st.caption("🔒 *차장 직급은 항목 추가 및 수정만 가능하며, 삭제는 부장 및 회장·부회장만 가능합니다.*")

            st.markdown("---")
            comments = it.get("comments", [])
            st.markdown(f"**💬 임원 코멘트 / 피드백 ({len(comments)})**")
            for cm in comments:
                st.markdown(f"- **{cm.get('author')}** *({cm.get('date')})* : {cm.get('text')}")

            cc1, cc2 = st.columns([4.2, 1])
            new_cm = cc1.text_input("코멘트 입력", placeholder="의견이나 확인 코멘트를 남겨주세요.", label_visibility="collapsed", key=f"cm_in_{item_id}")
            if cc2.button("💬 등록", key=f"cm_btn_{item_id}", use_container_width=True):
                if new_cm.strip():
                    comments.append({
                        "author": f"{user_name} ({user_dept}·{ROLES.get(user_role, '')})",
                        "text": new_cm.strip(),
                        "date": datetime.now().strftime("%m/%d %H:%M")
                    })
                    items[orig_idx]["comments"] = comments
                    save_json(DEPT_ITEMS_FILE, dept_items)
                    st.rerun()


# ==================== 8. 가시성 높은 카드형 홈 런처 & 개별 워크스페이스 라우터 ====================
DEPT_META = {
    "집행부": {"icon": "⚡", "color": "#38bdf8", "desc": "집행부 체크리스트, 월별 학생회 행사 일정 및 전 부서 월별 기획안 통합 보관"},
    "기획부": {"icon": "📋", "color": "#818cf8", "desc": "신규 행사 기획안 작성, AI 당일 큐시트·타임테이블 설계 및 지난 행사 자료함"},
    "운영부": {"icon": "📦", "color": "#34d399", "desc": "학생회 운영 창고 물품 실시간 수량·상태 점검 및 신규 구매 필요 항목 관리"},
    "총무부": {"icon": "💰", "color": "#fbbf24", "desc": "감사 대비 영수증·증빙 보관함, 월별 수입/지출 결산안 및 차기 총무 인수인계"},
    "복지부": {"icon": "🎁", "color": "#f472b6", "desc": "학우 대여용 복지물품 재고·대여 현황 및 간식드리미·사물함 등 복지 사업 관리"},
    "홍보부": {"icon": "📢", "color": "#c084fc", "desc": "카드뉴스·포스터 홍보물 원본 아카이브 및 카톡·인스타·에타 홍보 문구 제작"},
    "자율(자유전공)부": {"icon": "🏫", "color": "#22d3ee", "desc": "학교 본부 및 학부 주요 공지·학사 소식 정리 및 타 부서 협업 보조 업무 현황"}
}

dept_keys_ordered = ["집행부", "기획부", "운영부", "총무부", "복지부", "홍보부", "자율(자유전공)부"]

if st.session_state.active_page == "HOME":
    st.markdown("### 🧭 부서별 워크스페이스 & 실무 센터 선택")
    st.caption("원하시는 부서 또는 기능 카드의 **[입장하기]** 버튼을 누르면 해당 부서 전용 화면으로 넓고 쾌적하게 이동합니다.")

    # 3열 그리드로 7개 부서 + 월별 통합 회의자료 + 관리 센터 총 9개 대형 카드 배치
    all_cards = []
    for d_name in dept_keys_ordered:
        meta = DEPT_META[d_name]
        mods = DEPT_MODULES[d_name]
        # 열람 가능한 게시글 수 집계
        vis_cnt = 0
        for m in mods:
            for it in dept_items.get(d_name, {}).get(m["key"], []):
                if can_view_item(user_role, user_dept, d_name, it.get("is_shared", True)):
                    vis_cnt += 1
        all_cards.append({
            "page_key": d_name,
            "title": f"{meta['icon']} {d_name}",
            "color": meta["color"],
            "desc": meta["desc"],
            "pills": [m["name"] for m in mods],
            "badge": f"등록 {vis_cnt}건",
            "is_my": (user_dept == d_name),
            "btn_label": f"🚀 {d_name} 워크스페이스 입장" + (" (내 부서)" if user_dept == d_name else "")
        })

    all_cards.append({
        "page_key": "MEETING_HUB",
        "title": "📑 월별 통합 회의자료 & 회의록",
        "color": "#38bdf8",
        "desc": "월말·월초 부서별 @월 기획안·보고서 원클릭 통합본 생성, 표준 양식함 및 AI 실무 비서",
        "pills": ["📑 월별 회의자료 통합", "📄 표준 양식함", "📝 누적 회의록", "💬 AI 실무 비서"],
        "badge": f"통합자료 {len(meeting_docs_data)}건",
        "is_my": False,
        "btn_label": "📑 월별 회의자료 & 회의록 입장"
    })

    all_cards.append({
        "page_key": "ADMIN_SETTINGS",
        "title": "👑 관리 · 로고 · 디자인 설정",
        "color": "#fb7185",
        "desc": "대표 로고 이미지 업로드, 실버/커스텀 배경 그라데이션 설정 및 임원진 5단계 직급 관리",
        "pills": ["🖼️ 대표 로고·워터마크", "🎨 배경 그라데이션", "👥 임원 권한 관리", "🔧 AI 키 설정"],
        "badge": "회장·부회장 전용" if is_presidency(user_role) else "열람 제한",
        "is_my": is_presidency(user_role),
        "btn_label": "👑 관리 · 디자인 설정 센터 입장"
    })

    for row_start in range(0, len(all_cards), 3):
        cols = st.columns(3)
        for c_idx, card in enumerate(all_cards[row_start:row_start + 3]):
            with cols[c_idx]:
                my_cls = "dept-card dept-card-my" if card["is_my"] else "dept-card"
                pills_html = "".join(f'<span class="mod-pill">{p}</span>' for p in card["pills"])
                render_html(f"""
                <div class="{my_cls}" style="--card-accent: {card['color']};">
                    <div class="dept-card-title">
                        <span>{card['title']}</span>
                        <span class="role-badge" style="font-size:0.72rem;">{card['badge']}</span>
                    </div>
                    <div class="dept-card-desc">{card['desc']}</div>
                    <div>{pills_html}</div>
                </div>
                """)
                if st.button(card["btn_label"], key=f"go_card_{card['page_key']}", type="primary" if card["is_my"] else "secondary", use_container_width=True):
                    st.session_state.active_page = card["page_key"]
                    st.session_state.active_sub_idx = 0
                    st.rerun()
                st.write("")

elif st.session_state.active_page in dept_keys_ordered:
    d_name = st.session_state.active_page
    meta = DEPT_META[d_name]
    mods = DEPT_MODULES[d_name]

    top_c1, top_c2 = st.columns([3.5, 1])
    top_c1.subheader(f"{meta['icon']} {d_name} 전용 워크스페이스")
    if top_c2.button("⬅️ 전체 부서 홈으로 돌아가기", key=f"back_home_{d_name}", use_container_width=True):
        st.session_state.active_page = "HOME"
        st.rerun()

    st.markdown("##### 📂 세부 기능 선택 (버튼을 클릭해 이동하세요)")
    m_cols = st.columns(len(mods))
    if st.session_state.active_sub_idx >= len(mods):
        st.session_state.active_sub_idx = 0

    for s_idx, m_info in enumerate(mods):
        cnt = sum(1 for it in dept_items.get(d_name, {}).get(m_info["key"], []) if can_view_item(user_role, user_dept, d_name, it.get("is_shared", True)))
        btn_txt = f"{m_info['name']} ({cnt})"
        is_sel = (st.session_state.active_sub_idx == s_idx)
        if m_cols[s_idx].button(btn_txt, key=f"sub_btn_{d_name}_{s_idx}", type="primary" if is_sel else "secondary", use_container_width=True):
            st.session_state.active_sub_idx = s_idx
            st.rerun()

    st.markdown("---")
    selected_mod = mods[st.session_state.active_sub_idx]
    render_module_board(d_name, selected_mod)


# ==================== [Tab 8] 월별 통합 회의자료 제작소 & 양식 관리 & 회의록 ====================
elif st.session_state.active_page == "MEETING_HUB":
    top_c1, top_c2 = st.columns([3.5, 1])
    top_c1.subheader("📑 월별 정기회의 통합 회의자료 & 회의록 센터")
    if top_c2.button("⬅️ 전체 부서 홈으로 돌아가기", key="back_home_mtg", use_container_width=True):
        st.session_state.active_page = "HOME"
        st.rerun()
    st.markdown("---")
    mtg_menus = [
        "📑 월별 정기회의 통합 회의자료 제작소",
        "📄 기획안·보고서 표준 양식 관리함",
        "📝 누적 회의록 보관함",
        "💬 만능 AI 공문·섭외·민원 비서"
    ]
    mb_cols = st.columns(4)
    for m_i, m_label in enumerate(mtg_menus):
        if mb_cols[m_i].button(m_label, key=f"mtg_sub_btn_{m_i}", type="primary" if st.session_state.active_sub_idx == m_i else "secondary", use_container_width=True):
            st.session_state.active_sub_idx = m_i
            st.rerun()
    st.markdown("")

    if st.session_state.active_sub_idx == 0:
        st.subheader("📑 월말·월초 정기회의용 부서별 기획안/보고서 원클릭 통합기")
        st.caption("각 부서(집행부~자율부)에서 등록한 `@월` 기획안·보고서·첨부파일을 자동으로 수집하여 **하나의 통합 회의자료 문서**로 합쳐줍니다.")

        mc1, mc2, mc3 = st.columns([1.2, 1.2, 1.6])
        cur_m_label = f"{datetime.now().month}월"
        m_only_list = [f"{m}월" for m in range(1, 13)]
        sel_mtg_month = mc1.selectbox("📅 통합할 회의 대상 월 선택", m_only_list, index=m_only_list.index(cur_m_label) if cur_m_label in m_only_list else 0)
        sel_mtg_timing = mc2.selectbox("⏱️ 회의 구분", ["월초 정기회의 (이달의 기획안 점검)", "월말 정기회의 (이달의 결과보고 및 차월 준비)", "임시/확대 운영위원회 회의"])
        mtg_custom_title = mc3.text_input("회의자료 공식 제목", value=f"{cfg['year']}학년도 {cfg['council_name']} [{sel_mtg_month}] {sel_mtg_timing.split(' ')[0]} 통합 회의자료")

        collected_by_dept = {}
        attached_files_list = []
        total_collected_cnt = 0

        for d_name in dept_keys_ordered:
            d_mods = dept_items.get(d_name, {})
            dept_matched = []
            for m_info in DEPT_MODULES[d_name]:
                m_key = m_info["key"]
                for it in d_mods.get(m_key, []):
                    if it.get("target_month") == sel_mtg_month and it.get("include_in_meeting", True):
                        if can_view_item(user_role, user_dept, d_name, it.get("is_shared", True)):
                            dept_matched.append((m_info["name"], it))
                            total_collected_cnt += 1
                            if it.get("attachment"):
                                attached_files_list.append((d_name, it.get("title"), it.get("attachment")))
            if dept_matched:
                collected_by_dept[d_name] = dept_matched

        st.info(f"📊 현재 **[{sel_mtg_month}]** 통합 대상 안건: 총 **{len(collected_by_dept)}개 부서 / {total_collected_cnt}건**의 기획안·보고서 (첨부파일 **{len(attached_files_list)}개**)가 감지되었습니다.")

        with st.expander(f"➕ [{sel_mtg_month}] 우리 부서({user_dept}) 회의용 기획안/보고서 여기서 바로 제출·첨부하기", expanded=False):
            if not can_create_or_edit(user_role, user_dept, user_dept):
                st.warning("부서 기획안/보고서 제출은 부장·차장·회장단 권한에서 가능합니다.")
            else:
                q_tpl_names = ["(양식 미선택)"] + [t["name"] for t in templates_data]
                q_sel_tpl = st.selectbox("📄 적용할 표준 양식 선택", q_tpl_names, key="q_mtg_tpl")
                q_body_init = ""
                if q_sel_tpl != "(양식 미선택)":
                    for t in templates_data:
                        if t["name"] == q_sel_tpl:
                            q_body_init = t.get("content", "")
                            break
                q_dept = st.selectbox("제출 부서", cfg["departments"], index=cfg["departments"].index(user_dept) if user_dept in cfg["departments"] else 0, key="q_mtg_dept")
                q_title = st.text_input("안건/기획안/보고서 제목", placeholder=f"예: [{sel_mtg_month}] {q_dept} 월간 사업 기획안 및 보고서", key="q_mtg_title")
                q_content = st.text_area("기획안/보고서 내용 작성", value=q_body_init, height=150, key="q_mtg_content")
                q_file = st.file_uploader("📎 부서 기획안/보고서 원본 파일 첨부", key="q_mtg_file")

                if st.button(f"📥 [{sel_mtg_month}] 통합 회의자료 안건으로 즉시 제출", type="primary", use_container_width=True):
                    if not q_title.strip():
                        st.warning("안건 제목을 입력해주세요.")
                    else:
                        saved_fn = ""
                        if q_file is not None:
                            saved_fn = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{q_file.name}"
                            (FILES_DIR / saved_fn).write_bytes(q_file.getvalue())
                        first_mod_key = DEPT_MODULES[q_dept][0]["key"]
                        first_mod_name = DEPT_MODULES[q_dept][0]["name"]
                        dept_items.setdefault(q_dept, {}).setdefault(first_mod_key, []).insert(0, {
                            "id": f"item_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                            "title": q_title.strip(),
                            "target_month": sel_mtg_month,
                            "include_in_meeting": True,
                            "content": q_content.strip(),
                            "author": f"{user_name} ({ROLES.get(user_role, '')})",
                            "author_id": uid,
                            "dept": q_dept,
                            "mod_name": first_mod_name,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "is_shared": True,
                            "extra": {},
                            "attachment": saved_fn,
                            "comments": []
                        })
                        save_json(DEPT_ITEMS_FILE, dept_items)
                        st.success(f"[{sel_mtg_month}] {q_dept} 안건이 제출되어 통합 회의자료에 반영되었습니다!")
                        st.rerun()

        b_gen1, b_gen2 = st.columns(2)
        if b_gen1.button(f"📑 [{sel_mtg_month}] 부서별 취합 통합 회의자료 즉시 생성 (원문 통합)", type="primary", use_container_width=True):
            lines = [
                f"# 🏛️ {mtg_custom_title}",
                f"- **생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M')} | **작성자**: {user_name} ({ROLES.get(user_role, '')})",
                f"- **회의 구분**: {sel_mtg_timing} | **수집 안건 수**: 총 {len(collected_by_dept)}개 부서 {total_collected_cnt}건",
                "---",
                "## 📋 1. 부서별 상정 안건 목차"
            ]
            if not collected_by_dept:
                lines.append(f"\n> ⚠️ 아직 `{sel_mtg_month}`로 지정된 부서별 기획안/보고서가 없습니다. 각 부서 탭이나 위 제출창에서 `{sel_mtg_month}` 안건을 등록해주세요.")
            else:
                for d_idx, (d_name, d_list) in enumerate(collected_by_dept.items(), start=1):
                    lines.append(f"- **{d_idx}. {d_name}** ({len(d_list)}건): " + ", ".join(x[1].get("title", "") for x in d_list))

                lines.append("\n---\n## 🗂️ 2. 부서별 세부 기획안 및 보고서 본문")
                for d_name, d_list in collected_by_dept.items():
                    lines.append(f"\n### 🏛️ [{d_name}] 상정 안건 ({len(d_list)}건)")
                    for sub_idx, (m_label, it) in enumerate(d_list, start=1):
                        att_str = f" *(첨부파일: `{it.get('attachment').split('_', 2)[-1]}`)*" if it.get("attachment") else ""
                        lines.append(f"#### ({sub_idx}) [{m_label}] {it.get('title')}{att_str}")
                        lines.append(f"- **작성자**: {it.get('author')} | **등록일**: {it.get('created_at')}")
                        if it.get("extra"):
                            ex_pairs = [f"{k}: {v}" for k, v in it["extra"].items() if v]
                            if ex_pairs:
                                lines.append(f"- **세부 항목**: {' / '.join(ex_pairs)}")
                        lines.append("\n" + (it.get("content") or "*(본문 내용 없음)*") + "\n")

            merged_md = "\n".join(lines)
            meeting_docs_data.insert(0, {
                "title": mtg_custom_title,
                "month": sel_mtg_month,
                "timing": sel_mtg_timing,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "author": user_name,
                "content": merged_md,
                "attachments": attached_files_list
            })
            save_json(MEETING_DOCS_FILE, meeting_docs_data)
            st.success("통합 회의자료가 생성되어 아래 보관함에 저장되었습니다!")
            st.rerun()

        if b_gen2.button(f"🤖 AI로 [{sel_mtg_month}] 전 부서 안건 요약 브리핑 + 통합 회의자료 생성", use_container_width=True):
            if not collected_by_dept:
                st.warning(f"먼저 [{sel_mtg_month}]에 해당하는 부서별 기획안/보고서를 1건 이상 등록해주세요.")
            else:
                with st.spinner("전 부서 기획안/보고서를 통합하고 AI 핵심 회의 안건 브리핑을 작성 중입니다..."):
                    try:
                        raw_bundle = []
                        for d_name, d_list in collected_by_dept.items():
                            for m_label, it in d_list:
                                raw_bundle.append(f"[{d_name} - {m_label}] 제목: {it.get('title')}\n내용: {it.get('content')}")
                        sys_p = f"너는 {cfg['council_name']}의 집행부 수석 정책국장이야. 각 부서가 제출한 월별 기획안/보고서를 바탕으로 1) 이번 회의 핵심 안건 요약표, 2) 부서 간 협조 및 의사결정이 필요한 쟁점 사항, 3) 부서별 상세 보고 정리본이 포함된 완벽한 월별 정기회의 공식 회의자료를 작성해."
                        ai_doc = call_ai(sys_p, f"회의명: {mtg_custom_title}\n\n수집된 부서별 안건:\n" + "\n\n".join(raw_bundle), temp=0.25)
                        meeting_docs_data.insert(0, {
                            "title": f"[AI 브리핑 통합] {mtg_custom_title}",
                            "month": sel_mtg_month,
                            "timing": sel_mtg_timing,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "author": user_name,
                            "content": ai_doc,
                            "attachments": attached_files_list
                        })
                        save_json(MEETING_DOCS_FILE, meeting_docs_data)
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI 요약 실패: {e}")

        if meeting_docs_data:
            st.divider()
            st.markdown("#### 📂 생성된 월별 통합 회의자료 아카이브")
            for idx, doc in enumerate(meeting_docs_data):
                with st.expander(f"📑 [{doc.get('month')}] {doc.get('title')} ({doc.get('created_at')})", expanded=(idx == 0)):
                    st.markdown(doc.get("content", ""))

                    atts = doc.get("attachments", [])
                    if atts:
                        st.markdown("---")
                        st.markdown(f"**📎 이 달에 각 부서에서 첨부한 원본 파일 모음 ({len(atts)}건)**")
                        for a_idx, (a_dept, a_title, a_fn) in enumerate(atts):
                            ap = FILES_DIR / a_fn
                            if ap.exists():
                                orig_name = a_fn.split("_", 2)[-1]
                                st.download_button(
                                    f"📥 [{a_dept}] {a_title} — 첨부파일: {orig_name}",
                                    data=ap.read_bytes(),
                                    file_name=orig_name,
                                    key=f"mtg_att_{idx}_{a_idx}"
                                )

                    d_col1, d_col2, d_col3 = st.columns([2, 2, 1])
                    d_col1.download_button(
                        "📥 통합 회의자료 마크다운(.md) 다운로드",
                        data=doc.get("content", ""),
                        file_name=f"{doc.get('title')}.md",
                        mime="text/markdown",
                        key=f"dl_mdoc_md_{idx}",
                        use_container_width=True
                    )
                    html_export = f"""<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>{doc.get('title')}</title>
                    <style>body{{font-family:'Malgun Gothic',sans-serif;max-width:900px;margin:40px auto;line-height:1.65;color:#1e293b;padding:0 20px;}}
                    h1,h2,h3{{color:#0f172a;border-bottom:1px solid #cbd5e1;padding-bottom:6px;}} pre,code{{background:#f1f5f9;padding:4px;border-radius:4px;}}</style>
                    </head><body><pre style='white-space:pre-wrap;font-family:inherit;'>{doc.get('content', '')}</pre></body></html>"""
                    d_col2.download_button(
                        "🖨️ 인쇄/PDF 변환용 웹문서(.html) 다운로드",
                        data=html_export.encode("utf-8"),
                        file_name=f"{doc.get('title')}.html",
                        mime="text/html",
                        key=f"dl_mdoc_html_{idx}",
                        use_container_width=True
                    )
                    if is_presidency(user_role) and d_col3.button("🗑️ 삭제", key=f"del_mdoc_{idx}", use_container_width=True):
                        meeting_docs_data.pop(idx)
                        save_json(MEETING_DOCS_FILE, meeting_docs_data)
                        st.rerun()

    elif st.session_state.active_sub_idx == 1:
        st.subheader("📄 부서 공통 기획안·보고서 양식(템플릿) 보관 및 추가")
        if is_presidency(user_role) or user_role == "director":
            with st.expander("➕ 새 기획안 / 보고서 표준 양식 추가하기", expanded=False):
                t_name = st.text_input("양식 이름", placeholder="예: 2027 학생회 공식 월말 결과보고서 양식 (v2)")
                t_type = st.selectbox("양식 종류", ["기획안", "결과보고서", "결산안", "기타 표준양식"])
                t_body = st.text_area("양식 기본 본문 뼈대", height=150)
                t_file = st.file_uploader("📎 원본 양식 파일 업로드 (선택 - HWP, DOCX, XLSX 등)", key="tpl_up_file")

                if st.button("💾 새 표준 양식 등록", type="primary"):
                    if t_name.strip():
                        saved_tf = ""
                        if t_file is not None:
                            saved_tf = f"tpl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{t_file.name}"
                            (TEMPLATES_DIR / saved_tf).write_bytes(t_file.getvalue())
                        templates_data.append({
                            "id": f"tpl_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            "name": t_name.strip(),
                            "type": t_type,
                            "content": t_body.strip(),
                            "file": saved_tf
                        })
                        save_json(TEMPLATES_FILE, templates_data)
                        st.success("새 표준 양식이 등록되었습니다!")
                        st.rerun()

        for t_idx, tpl in enumerate(templates_data):
            with st.expander(f"📄 [{tpl.get('type', '양식')}] {tpl.get('name')}", expanded=(t_idx == 0)):
                st.code(tpl.get("content", ""), language="markdown")
                if tpl.get("file"):
                    tp_path = TEMPLATES_DIR / tpl["file"]
                    if tp_path.exists():
                        orig_tn = tpl["file"].split("_", 2)[-1]
                        st.download_button(f"📥 원본 양식 파일 다운로드 ({orig_tn})", data=tp_path.read_bytes(), file_name=orig_tn, key=f"dl_tpl_{t_idx}")
                if is_presidency(user_role) and st.button("🗑️ 이 양식 삭제", key=f"del_tpl_{t_idx}"):
                    templates_data.pop(t_idx)
                    save_json(TEMPLATES_FILE, templates_data)
                    st.rerun()

    elif st.session_state.active_sub_idx == 2:
        if is_presidency(user_role):
            st.subheader("📝 전체 누적 회의록 관리 센터 (회장·부회장 전용 전체 열람)")
            mt_c1, mt_c2 = st.columns([3, 1])
            mt_title = mt_c1.text_input("회의명 / 일자", placeholder="예: 3월 말 정기 중앙집행위원회 회의록")
            mt_shared = mt_c2.checkbox("🔓 일반 임원에게도 공개", value=False)
            mt_raw = st.text_area("회의 속기록 / 메모 붙여넣기", height=130)
            if st.button("✨ AI 공식 회의록 정리 및 저장", type="primary"):
                if mt_title.strip() and mt_raw.strip():
                    with st.spinner("공식 회의록으로 구조화 중입니다..."):
                        try:
                            sys_p = f"너는 {cfg['council_name']}의 수석 서기야. 회의 메모를 공식 회의록(안건별 결정사항, 부서별 To-Do 표, 차기 일정)으로 정리해."
                            clean_mt = call_ai(sys_p, f"회의명: {mt_title}\n원본 메모:\n{mt_raw}", temp=0.25)
                            minutes_data.insert(0, {
                                "title": mt_title.strip(),
                                "author": user_name,
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "is_shared": bool(mt_shared),
                                "content": clean_mt
                            })
                            save_json(MINUTES_FILE, minutes_data)
                            st.rerun()
                        except Exception as e:
                            st.error(f"회의록 생성 실패: {e}")

            st.divider()
            for i, m in enumerate(minutes_data):
                sh_txt = "🔓전체공개" if m.get("is_shared") else "🔒회장·부회장전용"
                with st.expander(f"📝 [{sh_txt}] {m.get('title')} ({m.get('date')})", expanded=(i == 0)):
                    st.markdown(m.get("content", ""))
                    if st.button("🗑️ 회의록 삭제", key=f"del_mt_{i}"):
                        minutes_data.pop(i)
                        save_json(MINUTES_FILE, minutes_data)
                        st.rerun()
        else:
            st.info("🔒 전체 누적 회의록 통계 및 비공개 회의록은 보안상 **회장·부회장**만 열람할 수 있습니다.")
            shared_mts = [m for m in minutes_data if m.get("is_shared")]
            for i, m in enumerate(shared_mts):
                with st.expander(f"📝 {m.get('title')} ({m.get('date')})"):
                    st.markdown(m.get("content", ""))

    elif st.session_state.active_sub_idx == 3:
        st.subheader("💬 학생회 만능 AI 실무 비서")
        q_type = st.radio(
            "문서 카테고리",
            ["🏛️ 교학팀/학생처 대관·예산 협조 공문", "🎤 외부 업체/푸드트럭/연사 섭외 요청문", "🤝 학우 건의사항/민원 공식 답변문", "📘 차기 기수 종합 인수인계 바이블 생성"],
            horizontal=True
        )
        user_ask = st.text_area("요청할 세부 상황을 적어주세요", height=110)
        if st.button("⚡ AI 실무 문서 즉시 생성", type="primary"):
            if user_ask.strip():
                with st.spinner("문서를 작성 중입니다..."):
                    try:
                        sys_p = f"너는 {cfg['year']}학년도 {cfg['generation']} {cfg['council_name']}의 수석 비서실장이야. ({q_type}) 양식에 맞춰 격식 있고 완성도 높은 문서를 작성해."
                        st.markdown(call_ai(sys_p, user_ask))
                    except Exception as e:
                        st.error(f"생성 안내: {e}")



# ==================== [Tab 9] 관리·디자인 설정 (실버 그라데이션 + 직접 배경 컬러 피커 포함) ====================
elif st.session_state.active_page == "ADMIN_SETTINGS":
    top_c1, top_c2 = st.columns([3.5, 1])
    top_c1.subheader("👑 학생회 브랜딩 · 배경 디자인 · 임원진 보안 관리 센터")
    if top_c2.button("⬅️ 전체 부서 홈으로 돌아가기", key="back_home_adm", use_container_width=True):
        st.session_state.active_page = "HOME"
        st.rerun()
    st.markdown("---")
    st.subheader("👑 학생회 브랜딩(로고 이미지) · 배경 그라데이션 디자인 · 임원진 보안 관리 센터")

    if not is_presidency(user_role):
        st.error("🔒 **보안 제한 구역:** 임원진 명단(리스트)과 시스템 디자인/기수 설정은 **회장·부회장**만 접근 및 열람할 수 있습니다.")
    else:
        adm_col1, adm_col2 = st.columns([1.08, 1.12])

        with adm_col1:
            st.markdown("#### 🖼️ 1. 대표 로고 이미지 파일 & 배경 워터마크 설정")
            up_logo = st.file_uploader("대표 로고 이미지 업로드 (투명 배경 PNG 권장)", type=["png", "jpg", "jpeg", "webp", "svg"])
            wm_op = st.slider("배경 로고 워터마크 은은함(투명도) 조절", min_value=0.0, max_value=0.20, value=float(cfg.get("watermark_opacity", 0.06)), step=0.01)

            l_c1, l_c2 = st.columns(2)
            if l_c1.button("🖼️ 로고 이미지 및 투명도 적용", type="primary", use_container_width=True):
                if up_logo is not None:
                    ext = Path(up_logo.name).suffix.lower()
                    logo_fn = f"council_logo{ext}"
                    (LOGO_DIR / logo_fn).write_bytes(up_logo.getvalue())
                    cfg["logo_file"] = logo_fn
                cfg["watermark_opacity"] = wm_op
                save_json(CONFIG_FILE, cfg)
                st.success("대표 로고 이미지와 배경 블렌딩이 적용되었습니다!")
                st.rerun()

            if cfg.get("logo_file") and l_c2.button("🗑️ 이미지 로고 제거", use_container_width=True):
                cfg["logo_file"] = ""
                save_json(CONFIG_FILE, cfg)
                st.rerun()

            st.divider()
            st.markdown("#### 🎨 2. 기수 · 배경 그라데이션 & 실버 테마 컬러 커스텀")
            new_year = st.text_input("활동 연도", value=cfg["year"])
            new_gen = st.text_input("기수 표기", value=cfg["generation"])
            new_cname = st.text_input("학생회 공식 명칭", value=cfg["council_name"])
            new_slogan = st.text_input("학생회 슬로건", value=cfg["slogan"])
            new_emoji = st.text_input("보조 로고 이모지", value=cfg.get("logo_emoji", "🏛️"))

            t_keys = list(THEME_PRESETS.keys())
            cur_t_idx = t_keys.index(cfg["theme_key"]) if cfg.get("theme_key") in t_keys else 0
            new_theme = st.selectbox("배경 테마 프리셋 선택 (실버 그라데이션 2종 포함)", options=t_keys, index=cur_t_idx, format_func=lambda k: THEME_PRESETS[k]["name"])

            use_custom_bg = st.checkbox("🌈 배경 그라데이션 색상 직접 정하기 (3단 그라데이션 + 사이드바 색상)", value=bool(cfg.get("use_custom_bg", False)))
            if use_custom_bg:
                bg_c1, bg_c2, bg_c3, bg_c4 = st.columns(4)
                custom_bg1 = bg_c1.color_picker("배경 시작색", value=cfg.get("custom_bg_color1", "#11141a"))
                custom_bg2 = bg_c2.color_picker("배경 중간색", value=cfg.get("custom_bg_color2", "#2b323f"))
                custom_bg3 = bg_c3.color_picker("배경 끝색", value=cfg.get("custom_bg_color3", "#475263"))
                custom_sb = bg_c4.color_picker("사이드바 배경", value=cfg.get("custom_sidebar_color", "#141820"))
            else:
                custom_bg1 = cfg.get("custom_bg_color1", "#11141a")
                custom_bg2 = cfg.get("custom_bg_color2", "#2b323f")
                custom_bg3 = cfg.get("custom_bg_color3", "#475263")
                custom_sb = cfg.get("custom_sidebar_color", "#141820")

            use_custom = st.checkbox("✨ 테두리·강조 포인트 컬러 직접 지정 (Hex)", value=bool(cfg.get("use_custom_color", False)))
            custom_col = st.color_picker("메인 포인트 컬러 선택", value=cfg.get("custom_primary", "#e2e8f0")) if use_custom else cfg.get("custom_primary", "#e2e8f0")

            if st.button("💾 기수 & 배경 디자인 설정 즉시 적용", type="primary", use_container_width=True):
                cfg.update({
                    "year": new_year.strip(),
                    "generation": new_gen.strip(),
                    "council_name": new_cname.strip(),
                    "slogan": new_slogan.strip(),
                    "logo_emoji": new_emoji.strip() or "🏛️",
                    "theme_key": new_theme,
                    "use_custom_bg": use_custom_bg,
                    "custom_bg_color1": custom_bg1,
                    "custom_bg_color2": custom_bg2,
                    "custom_bg_color3": custom_bg3,
                    "custom_sidebar_color": custom_sb,
                    "use_custom_color": use_custom,
                    "custom_primary": custom_col
                })
                save_json(CONFIG_FILE, cfg)
                st.success("배경 그라데이션 및 디자인 설정이 적용되었습니다!")
                st.rerun()

        with adm_col2:
            st.markdown("#### 👥 3. 임원진 리스트 & 5단계 직급·부서 권한 관리")
            with st.expander("➕ 신규 임원 계정 직접 발급하기", expanded=False):
                mk_id = st.text_input("부여할 아이디 (ID)", key="mk_id")
                mk_pw = st.text_input("초기 비밀번호 (Password)", key="mk_pw")
                mk_name = st.text_input("임원 이름", key="mk_name")
                mk_dept = st.selectbox("배정 부서", cfg["departments"], key="mk_dept")
                mk_role = st.selectbox("배정 직급", list(ROLES.keys()), format_func=lambda k: ROLES[k], index=4, key="mk_role")
                if st.button("✨ 임원 계정 즉시 발급", type="primary", use_container_width=True):
                    mid = mk_id.strip()
                    if mid and mk_pw and mk_name.strip():
                        if mid in accounts:
                            st.error("이미 존재하는 아이디입니다.")
                        else:
                            accounts[mid] = {
                                "pw_hash": hash_pw(mk_pw),
                                "pw_plain": mk_pw,
                                "name": mk_name.strip(),
                                "dept": mk_dept,
                                "role": mk_role,
                                "api_key": "",
                                "joined_at": datetime.now().strftime("%Y-%m-%d")
                            }
                            save_json(ACCOUNTS_FILE, accounts)
                            st.success(f"{mk_name} 님의 계정이 발급되었습니다!")
                            st.rerun()

            for acc_id, acc_data in list(accounts.items()):
                r_code = acc_data.get("role", "member")
                with st.expander(f"{ROLES.get(r_code, '🌱 부원')} | {acc_data.get('name')} — [{acc_data.get('dept')}]", expanded=False):
                    u_name = st.text_input("이름 수정", value=acc_data.get("name", ""), key=f"un_{acc_id}")
                    d_opts = cfg["departments"]
                    d_idx = d_opts.index(acc_data.get("dept")) if acc_data.get("dept") in d_opts else 0
                    u_dept = st.selectbox("소속 부서 변경", options=d_opts, index=d_idx, key=f"ud_{acc_id}")

                    r_opts = list(ROLES.keys())
                    r_idx = r_opts.index(r_code) if r_code in r_opts else 4
                    u_role = st.selectbox("직급 변경 (5단계)", options=r_opts, index=r_idx, format_func=lambda k: ROLES[k], key=f"ur_{acc_id}")
                    u_pw = st.text_input("비밀번호 재설정 (변경 시에만 입력)", type="password", key=f"upw_{acc_id}")

                    b_c1, b_c2 = st.columns(2)
                    if b_c1.button("💾 직급/부서 저장", key=f"usave_{acc_id}", use_container_width=True):
                        accounts[acc_id]["name"] = u_name.strip()
                        accounts[acc_id]["dept"] = u_dept
                        accounts[acc_id]["role"] = u_role
                        if u_pw.strip():
                            accounts[acc_id]["pw_hash"] = hash_pw(u_pw.strip())
                            accounts[acc_id]["pw_plain"] = u_pw.strip()
                        save_json(ACCOUNTS_FILE, accounts)
                        st.success("저장 완료!")
                        st.rerun()
                    if acc_id != uid and b_c2.button("🗑️ 계정 삭제", key=f"udel_{acc_id}", use_container_width=True):
                        accounts.pop(acc_id, None)
                        save_json(ACCOUNTS_FILE, accounts)
                        st.rerun()

            if user_role == "president":
                st.divider()
                with st.expander("🕵️‍♂️ [회장 단독 기밀] 전 임원 아이디(ID) & 비밀번호(PW) 원문 마스터 조회함", expanded=False):
                    st.caption("※ 오직 👑 회장(president) 계정에서만 표시되며, 부회장을 포함한 타 임원에게는 이 메뉴의 존재 자체가 보이지 않습니다.")
                    secret_rows = []
                    for s_id, s_data in accounts.items():
                        secret_rows.append({
                            "직급": ROLES.get(s_data.get("role", "member"), ""),
                            "소속 부서": s_data.get("dept", ""),
                            "이름": s_data.get("name", ""),
                            "아이디 (ID)": s_id,
                            "비밀번호 (PW 원문)": s_data.get("pw_plain", "(로그인 시 자동 동기화됨)"),
                            "등록일": s_data.get("joined_at", "")
                        })
                    st.dataframe(secret_rows, use_container_width=True)

    # ---- [숨김 메뉴] AI 엔진 & API 키 설정 ----
    st.divider()
    with st.expander("🔧 [고급 숨김 설정] AI 엔진 (Argon / Gemini) & API 키 연동 관리", expanded=False):
        st.caption("홈 화면과 사이드바를 깔끔하게 유지하기 위해 이곳에 숨겨진 AI 엔진 설정창입니다.")
        hk1, hk2 = st.columns(2)
        with hk1:
            my_api_in = st.text_input("내 계정 전용 Gemini API Key", value=user_info.get("api_key", ""), type="password")
            if is_presidency(user_role):
                shared_api_in = st.text_input("학생회 전체 공용 Gemini API Key (회장·부회장 전용 설정)", value=cfg.get("shared_api_key", ""), type="password")
            else:
                shared_api_in = cfg.get("shared_api_key", "")

            if st.button("💾 API Key 저장", use_container_width=True):
                accounts[uid]["api_key"] = my_api_in.strip()
                save_json(ACCOUNTS_FILE, accounts)
                if is_presidency(user_role):
                    cfg["shared_api_key"] = shared_api_in.strip()
                    save_json(CONFIG_FILE, cfg)
                st.success("API Key가 저장되었습니다!")
                st.rerun()

        with hk2:
            if st.button("🔄 사용 가능한 최신 모델 목록 동기화", use_container_width=True):
                test_k = my_api_in.strip() or shared_api_in.strip()
                if not test_k:
                    st.error("API Key를 먼저 입력 후 저장해주세요.")
                else:
                    try:
                        cl = genai.Client(api_key=test_k)
                        models = sorted(list({
                            m.name.replace("models/", "")
                            for m in cl.models.list()
                            if getattr(m, "name", "") and "gemini" in m.name.lower() and "embedding" not in m.name.lower()
                        }), reverse=True)
                        if models:
                            cfg["available_models"] = models
                            save_json(CONFIG_FILE, cfg)
                            st.success(f"총 {len(models)}개 모델 동기화 완료!")
                    except Exception as e:
                        st.error(f"모델 조회 실패: {e}")

            m_list = cfg.get("available_models", ["gemini-2.5-flash", "gemini-2.5-pro"])
            def_idx = m_list.index(cfg["default_model"]) if cfg.get("default_model") in m_list else 0
            new_sel_model = st.selectbox("기본 작동 AI 모델 선택", options=m_list, index=def_idx)
            if new_sel_model != cfg.get("default_model"):
                cfg["default_model"] = new_sel_model
                save_json(CONFIG_FILE, cfg)
                st.rerun()
