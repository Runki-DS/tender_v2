import streamlit as st
import requests
import pandas as pd
import re
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ----------------------------------------------------------------------------
# 1. НАСТРОЙКА СТРАНИЦЫ
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Брусника — проверка контрагента",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="collapsed"
)

api_key = st.secrets.get("FOCUS_API_KEY", "")
if not api_key:
    st.warning("⚠️ API ключ Контур.Фокуса не настроен. Добавьте `FOCUS_API_KEY` в secrets приложения.")

# ЦВЕТА
BG_COLOR = "#f8f7f4"
WHITE = "#ffffff"
DARK = "#1e1e1e"
GRAY = "#6b6b6b"
LIGHT_GRAY = "#f0eeea"
BORDER_COLOR = "rgba(0, 0, 0, 0.05)"
GOLD = "#b89b7b"
GREEN = "#1d6b2e"
RED = "#b33a3a"
ORANGE = "#b8681a"
BLUE = "#1e5a8a"

st.markdown(f"""
<style>
    .stApp {{ background-color: {BG_COLOR}; font-family: 'Inter', sans-serif; }}
    .main > div {{ padding: 0; max-width: 1100px; margin: 0 auto; }}
    #MainMenu, footer, .stDeployButton, header {{ visibility: hidden; }}

    .header {{
        background: {WHITE}; padding: 20px 24px 12px;
        border-bottom: 1px solid {BORDER_COLOR};
        display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;
    }}
    .logo {{ display: flex; align-items: center; gap: 10px; color: {DARK}; }}
    .logo-icon {{ width: 36px; height: 36px; background: {DARK}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {WHITE}; font-weight: 700; font-size: 18px; }}
    .logo-text {{ font-weight: 600; font-size: 22px; letter-spacing: -0.3px; }}
    .logo-text span {{ font-weight: 300; color: {GRAY}; }}
    .header-tag {{ font-size: 14px; color: {GRAY}; background: {LIGHT_GRAY}; padding: 6px 16px; border-radius: 40px; }}

    .hero {{ padding: 48px 24px 32px; }}
    .hero h1 {{ font-size: 36px; font-weight: 400; letter-spacing: -0.4px; margin-bottom: 8px; line-height: 1.2; color: {DARK}; }}
    .hero h1 strong {{ font-weight: 600; }}
    .hero .sub {{ font-size: 18px; color: #4a4a4a; margin-bottom: 32px; }}

    .search-card {{
        background: {WHITE}; border-radius: 24px; padding: 36px 40px;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.04); border: 1px solid {BORDER_COLOR};
        margin-bottom: 24px;
    }}

    .results-card {{
        background: {WHITE}; border-radius: 24px; padding: 32px 36px;
        border: 1px solid {BORDER_COLOR}; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.04);
        margin-bottom: 20px;
    }}
    .winner-card {{ border-left: 6px solid {GREEN}; }}
    .reserve-card {{ border-left: 6px solid {BLUE}; }}
    .other-card {{ border-left: 6px solid {GRAY}; opacity: 0.95; }}

    .company-name {{ font-size: 22px; font-weight: 600; color: {DARK}; }}
    .company-inn {{ font-size: 15px; color: {GRAY}; margin-top: 2px; }}

    .result-grid {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 14px 28px; margin-top: 18px;
    }}
    .result-item {{ border-bottom: 1px solid {LIGHT_GRAY}; padding-bottom: 8px; }}
    .result-item .label {{ font-size: 11px; color: {GRAY}; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }}
    .result-item .value {{ font-size: 17px; font-weight: 500; color: {DARK}; }}

    .score-badge {{
        display: inline-block; padding: 4px 14px; border-radius: 20px;
        font-size: 14px; font-weight: 600; background: #e6f0e6; color: {GREEN};
    }}
    .score-badge.reserve {{ background: #e0ecf5; color: {BLUE}; }}
    .score-badge.other {{ background: {LIGHT_GRAY}; color: {GRAY}; }}

    .lot-header {{
        margin: 36px 0 14px; padding: 14px 20px;
        background: {WHITE}; border-radius: 14px;
        border-left: 5px solid {GOLD};
        font-size: 20px; font-weight: 600; color: {DARK};
    }}

    .footer {{
        margin-top: 40px; padding: 24px; border-top: 1px solid {BORDER_COLOR};
        background: {WHITE}; text-align: center; font-size: 14px; color: {GRAY};
    }}

    @media (max-width: 640px) {{
        .result-grid {{ grid-template-columns: 1fr; }}
        .search-card {{ padding: 24px 20px; }}
        .results-card {{ padding: 24px 20px; }}
    }}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# 2. ШАПКА
# ----------------------------------------------------------------------------
st.markdown("""
<div class="header">
    <div class="logo">
        <div class="logo-icon">Б</div>
        <div class="logo-text">Брусника <span>· проверка</span></div>
    </div>
    <span class="header-tag">Сравнение участников тендера</span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>Сравнение <strong>участников тендера</strong></h1>
    <p class="sub">Оценка надёжности и ценовых предложений по данным ФНС и Контур.Фокуса</p>
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# 3. ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ
# ----------------------------------------------------------------------------
if "parsed" not in st.session_state:
    st.session_state.parsed = None          # {'participants': [...], 'lots': [...]}
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False


# ============================================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ
# ============================================================================
def _norm(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def _to_number(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(",", ".")
    m = re.match(r"^-?\d+(\.\d+)?$", s)
    if m:
        return float(s)
    return None


# ============================================================================
# 5. ПАРСЕР EXCEL
# ============================================================================
def parse_tender_excel(file_like, sheet=0):
    """
    Возвращает:
      {
        'participants': [{'inn':..., 'name':..., 'prices': {lot_title: sum}}],
        'lots': [lot_title, ...],
      }
    """
    df = pd.read_excel(file_like, sheet_name=sheet, header=None, dtype=object)
    n_rows, n_cols = df.shape

    # ------------------------------------------------------------------
    # 1. Участники
    # ------------------------------------------------------------------
    participants = []
    header_row_participants = None

    # Формат B: (ИНН ...) в шапке
    for r in range(min(n_rows, 60)):
        found = []
        for c in range(n_cols):
            v = _norm(df.iat[r, c])
            if not v:
                continue
            m = re.search(r"\(?\s*ИНН\s*[:№]?\s*(\d{10}|\d{12})\s*\)?", v, flags=re.IGNORECASE)
            if m:
                inn = m.group(1)
                name_part = re.split(r"\(?\s*ИНН", v, flags=re.IGNORECASE)[0]
                name_part = name_part.strip(" \t\"'«»")
                found.append((c, inn, name_part or v))
        if len(found) >= 2:
            header_row_participants = r
            for col, inn, name in found:
                participants.append({"inn": inn, "name": name, "inn_col": col})
            break

    # Формат A: строка "ИНН"
    if not participants:
        inn_row = None
        for r in range(n_rows):
            for c in range(n_cols):
                if _norm(df.iat[r, c]).upper().startswith("ИНН"):
                    inn_row = r
                    break
            if inn_row is not None:
                break
        if inn_row is None:
            raise RuntimeError(
                "Не найдена ни строка 'ИНН', ни шапка с '(ИНН ...)'. "
                "Проверьте, что это таблица предложений."
            )

        name_row = None
        for r in range(n_rows):
            for c in range(n_cols):
                if "наименование контрагента" in _norm(df.iat[r, c]).lower():
                    name_row = r
                    break
            if name_row is not None:
                break

        inn_cells = []
        for c in range(n_cols):
            v = _norm(df.iat[inn_row, c]).replace(" ", "")
            if re.fullmatch(r"\d{10}(\d{2})?", v):
                inn_cells.append((c, v))

        if not inn_cells:
            raise RuntimeError("В строке 'ИНН' не найдено ни одного корректного ИНН")

        for inn_col, inn in inn_cells:
            firm = ""
            if name_row is not None:
                for dc in (0, -1, 1, 2, -2):
                    cc = inn_col + dc
                    if 0 <= cc < n_cols:
                        v = _norm(df.iat[name_row, cc])
                        if v and not v.isdigit() and len(v) > 3:
                            firm = v
                            break
            participants.append({"inn": inn, "name": firm, "inn_col": inn_col})

    # ------------------------------------------------------------------
    # 2. Определяем колонки сумм
    # ------------------------------------------------------------------
    # Ищем строку-шапку колонок: "Цена за ед." + "Сумма"
    header_row = None
    for r in range(n_rows):
        txt = " ".join(_norm(df.iat[r, c]).lower() for c in range(n_cols))
        if "цена за ед" in txt and ("сумма" in txt or "стоимость" in txt):
            header_row = r
            break

    # Резервная строка — "Система налогообложения"
    tax_row = None
    for r in range(n_rows):
        for c in range(n_cols):
            if "система налогообложения" in _norm(df.iat[r, c]).lower():
                tax_row = r
                break
        if tax_row is not None:
            break

    tax_cols = []
    if tax_row is not None:
        for c in range(n_cols):
            v = _norm(df.iat[tax_row, c]).lower()
            if "ндс" in v or "усн" in v:
                tax_cols.append(c)

    for p in participants:
        inn_col = p["inn_col"]
        sum_col = None

        if header_row is not None:
            # Идём вправо от колонки участника и ищем "сумма"/"стоимость всего"
            for c in range(inn_col, n_cols):
                hv = _norm(df.iat[header_row, c]).lower()
                if "сумма" in hv or "стоимость всего" in hv:
                    sum_col = c
                    break
            if sum_col is None:
                hv = _norm(df.iat[header_row, inn_col]).lower()
                if "сумма" in hv or "стоимость всего" in hv:
                    sum_col = inn_col

        if sum_col is None:
            for c in tax_cols:
                if c >= inn_col:
                    sum_col = c
                    break

        if sum_col is None:
            sum_col = inn_col

        p["sum_col"] = sum_col

    # ------------------------------------------------------------------
    # 3. Находим все лоты
    # ------------------------------------------------------------------
    lot_rows = []
    for r in range(n_rows):
        name_v = _norm(df.iat[r, 2])
        if name_v.lower().startswith("лот №"):
            lot_rows.append((r, name_v))

    if not lot_rows:
        raise RuntimeError("Не найдены строки лотов ('Лот №...')")

    # ------------------------------------------------------------------
    # 4. Суммы по лотам
    # ------------------------------------------------------------------
    STOP_WORDS = (
        "всего", "итого", "первоначальное предложение",
        "транспортные расходы", "порядок доставки",
        "предлагаемые условия", "статус поставщика",
        "кп соответствует", "согласен", "предупрежден",
        "заявка на участие", "дилерский сертификат",
        "документы о качестве", "отсрочка", "срок фиксации",
        "перечень представленных", "условия оплаты",
        "условия (базис)", "система налогообложения",
        "валюта предложения", "валюта конкурентного",
        "курс валюты", "результат проверки",
    )

    def is_stop_row(r):
        a = _norm(df.iat[r, 0]).lower()
        b = _norm(df.iat[r, 1]).lower() if n_cols > 1 else ""
        c = _norm(df.iat[r, 2]).lower() if n_cols > 2 else ""
        joined = f"{a} {b} {c}"
        for w in STOP_WORDS:
            if w in joined:
                return True
        return False

    lots = [t for _, t in lot_rows]

    for p in participants:
        p["prices"] = {}
        sc = p["sum_col"]
        for i, (r_start, lot_title) in enumerate(lot_rows):
            r_end = lot_rows[i + 1][0] if i + 1 < len(lot_rows) else n_rows
            total = 0.0
            for r in range(r_start + 1, r_end):
                if is_stop_row(r):
                    continue
                num = _to_number(df.iat[r, sc])
                if num is not None:
                    total += num
            p["prices"][lot_title] = total

    # Убираем дубли ИНН
    seen = set()
    uniq = []
    for p in participants:
        if p["inn"] in seen:
            continue
        seen.add(p["inn"])
        uniq.append(p)

    return {"participants": uniq, "lots": lots}


# ============================================================================
# 6. PDF
# ============================================================================
def _register_fonts():
    candidates = [
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("DejaVuSans", "/Library/Fonts/DejaVuSans.ttf"),
        ("DejaVuSans", "C:\\Windows\\Fonts\\DejaVuSans.ttf"),
        ("Arial", "C:\\Windows\\Fonts\\arial.ttf"),
        ("Arial", "/Library/Fonts/Arial.ttf"),
    ]
    for name, path in candidates:
        try:
            pdfmetrics.registerFont(TTFont(name, path))
            return name
        except Exception:
            continue
    return "Helvetica"


def build_pdf_report(df_all, lots_count, lot_titles=None):
    buf = io.BytesIO()
    font_name = _register_fonts()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="Отчёт по тендеру",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"],
                        fontName=font_name, fontSize=16, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                        fontName=font_name, fontSize=13, spaceAfter=8)
    normal = ParagraphStyle("N", parent=styles["Normal"],
                            fontName=font_name, fontSize=9, leading=12)
    small = ParagraphStyle("S", parent=styles["Normal"],
                           fontName=font_name, fontSize=8, leading=10,
                           textColor=colors.grey)

    story = []
    story.append(Paragraph("Отчёт по тендеру", h1))
    story.append(Paragraph(
        f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        small
    ))
    story.append(Spacer(1, 6 * mm))

    for lot_idx in range(lots_count):
        lot_title = lot_titles[lot_idx] if lot_titles and lot_idx < len(lot_titles) \
            else f"Лот {lot_idx + 1}"

        df_lot = calculate_lot_scores(df_all, lot_idx, lots_count)

        story.append(Paragraph(f"🧩 {lot_title}", h2))

        if df_lot.empty:
            story.append(Paragraph("Заявок по лоту не подано.", normal))
            story.append(Spacer(1, 6 * mm))
            continue

        header = ["#", "Компания", "ИНН", "Цена по лоту", "Сумма по лотам", "Баллы"]
        data = [header]
        for i, row in df_lot.iterrows():
            data.append([
                str(i + 1),
                Paragraph(str(row["name"]), normal),
                str(row["inn"]),
                f"{row['lot_price']:,.0f}",
                f"{row['price_total']:,.0f}",
                str(row["score"]),
            ])

        table = Table(data, colWidths=[10*mm, 60*mm, 28*mm, 28*mm, 30*mm, 15*mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0eeea")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e1e1e")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#fafafa")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 4 * mm))

        winner = df_lot.iloc[0]
        story.append(Paragraph(
            f"<b>🏆 Победитель:</b> {winner['name']} (ИНН {winner['inn']}) — "
            f"баллов {winner['score']}, цена по лоту {winner['lot_price']:,.0f} ₽",
            normal
        ))
        if len(df_lot) > 1:
            reserve = df_lot.iloc[1]
            story.append(Paragraph(
                f"<b>🔄 Резерв:</b> {reserve['name']} (ИНН {reserve['inn']}) — "
                f"баллов {reserve['score']}, цена по лоту {reserve['lot_price']:,.0f} ₽",
                normal
            ))

        story.append(Spacer(1, 8 * mm))
        if lot_idx < lots_count - 1:
            story.append(PageBreak())

    doc.build(story)
    buf.seek(0)
    return buf


# ============================================================================
# 7. КОНТУР.ФОКУС
# ============================================================================
def fetch_kontur_data(inn, api_key):
    result = {
        'inn': inn, 'name': 'Неизвестно', 'revenue': 0, 'employees': 0,
        'yellow_statements': 0, 'red_statements': 0, 'risk_text': [],
        'risk_markers': [], 'brief_href': '',
        'scoring_score': 0, 'max_debt': 0, 'cred_day': 0, 'equity': 0,
        'status': 'OK'
    }
    if not api_key:
        result['status'] = 'No API Key'
        return result

    SCORING_MODEL_IDS = {
        "304a90a4-8882-4be8-9c01-72e2b356179d",
        "7f5311e1-e7c0-4535-a85b-4bb2eebcee79",
        "3e64aa23-2653-412d-b072-c04a948e6402",
    }

    try:
        r = requests.get("https://focus-api.kontur.ru/api3/req",
                         params={"key": api_key, "inn": inn}, timeout=15)
        if r.status_code == 200 and r.json():
            req = r.json()[0]
            result['name'] = req.get('UL', {}).get('legalName', {}).get('short', 'Неизвестно')

        r = requests.get("https://focus-api.kontur.ru/api3/accountingReports",
                         params={"key": api_key, "inn": inn}, timeout=15)
        buh_forms = []
        if r.status_code == 200 and r.json():
            data = r.json()
            if data and len(data) > 0:
                buh_forms = data[0].get('buhForms', [])
                years = sorted([f.get('year') for f in buh_forms if f.get('year')], reverse=True)
                if years:
                    latest = next((f for f in buh_forms if f.get('year') == years[0]), None)
                    if latest:
                        for item in latest.get('form2', []):
                            if item.get('code') == 2110:
                                result['revenue'] = item.get('endValue', 0)
                                break

        try:
            r = requests.get("https://focus-api.kontur.ru/api3/legalAnalytics",
                             params={"key": api_key, "inn": inn}, timeout=15)
            if r.status_code == 200 and r.json():
                data = r.json()
                entry = data[0] if isinstance(data, list) and data else data
                legal = entry.get('legalAnalyticsData', {}) if isinstance(entry, dict) else {}

                staff_block = legal.get('staffNumber')
                if isinstance(staff_block, dict):
                    val = staff_block.get('data')
                    if val is not None:
                        try:
                            result['employees'] = int(val)
                        except (TypeError, ValueError):
                            pass

                if result['employees'] == 0:
                    hist_block = legal.get('historyStaffNumbers')
                    if isinstance(hist_block, dict):
                        hist = hist_block.get('data', []) or []
                        if hist:
                            def _d(rec):
                                return rec.get('date', '') if isinstance(rec, dict) else ''
                            last = sorted(hist, key=_d)[-1]
                            v = last.get('staffNumber') if isinstance(last, dict) else None
                            if v is not None:
                                try:
                                    result['employees'] = int(v)
                                except (TypeError, ValueError):
                                    pass
        except Exception:
            pass

        r = requests.get("https://focus-api.kontur.ru/api3/briefReport",
                         params={"key": api_key, "inn": inn}, timeout=15)
        if r.status_code == 200 and r.json():
            data = r.json()
            brief = data[0] if isinstance(data, list) else data
            brief_report = brief.get('briefReport', {}) or {}
            summary = brief_report.get('summary', {}) or {}
            href = brief_report.get('href', '')
            result['yellow_statements'] = 1 if summary.get('yellowStatements', False) else 0
            result['red_statements'] = 1 if summary.get('redStatements', False) else 0
            result['brief_href'] = href

        try:
            r = requests.get("https://focus-api.kontur.ru/api3/scoring",
                             params={"key": api_key, "inn": inn}, timeout=15)
            if r.status_code == 200 and r.json():
                data = r.json()
                scoring_list = data if isinstance(data, list) else [data]
                scoring_sum = 0
                risk_markers = []

                for entry in scoring_list:
                    if not isinstance(entry, dict):
                        continue
                    models = (
                        entry.get('scoringData', [])
                        or entry.get('scoring', [])
                        or entry.get('models', [])
                    )
                    for model in models:
                        if not isinstance(model, dict):
                            continue
                        model_id = model.get('modelId') or model.get('id')
                        if model_id in SCORING_MODEL_IDS:
                            rating = model.get('rating') or model.get('score') or 0
                            try:
                                scoring_sum += float(rating)
                            except (TypeError, ValueError):
                                pass

                        for m in model.get('triggeredMarkers', []) or []:
                            if not isinstance(m, dict):
                                continue
                            if m.get('impact') != 'Risk':
                                continue
                            name = m.get('name', '')
                            desc = m.get('description', '') or ''
                            weight = m.get('weight', '')
                            txt = name + (f" — {desc}" if desc else "")
                            if weight in ('High', 'Significant'):
                                risk_markers.append(('red', txt))
                            else:
                                risk_markers.append(('yellow', txt))

                result['scoring_score'] = round(scoring_sum, 2)
                result['risk_markers'] = risk_markers
        except Exception:
            pass

        for kind, txt in result.get('risk_markers', []):
            if kind == 'red':
                result['risk_text'].append(f"🔴 {txt}")
            else:
                result['risk_text'].append(f"⚠️ {txt}")

        if result['yellow_statements'] and not any(t.startswith('⚠️') for t in result['risk_text']):
            result['risk_text'].append("⚠️ Есть информация, помеченная жёлтым цветом")
        if result['red_statements'] and not any(t.startswith('🔴') for t in result['risk_text']):
            result['risk_text'].append("🔴 Есть информация, помеченная красным цветом")

        if result.get('brief_href'):
            result['risk_text'].append(
                f'🔗 <a href="{result["brief_href"]}" target="_blank" '
                f'style="color:#1e5a8a;">Открыть полный отчёт Контур.Фокуса</a>'
            )

        if buh_forms:
            years = sorted([f.get('year') for f in buh_forms if f.get('year')], reverse=True)
            last_year = years[0] if years else None

            def get_val(form, code, vtype='endValue'):
                for item in form:
                    if item.get('code') == code:
                        return item.get(vtype, 0)
                return 0

            if last_year:
                latest = next((f for f in buh_forms if f.get('year') == last_year), None)
                if latest:
                    f1 = latest.get('form1', [])
                    f2 = latest.get('form2', [])

                    eV_1230 = get_val(f1, 1230)
                    eV_2110 = get_val(f2, 2110)
                    eV_1520 = get_val(f1, 1520)
                    eV_1600 = get_val(f1, 1600)
                    eV_1400 = get_val(f1, 1400)
                    eV_1500 = get_val(f1, 1500)

                    NDS = 22
                    K1 = 1 + NDS / 100
                    K2 = 0.8

                    result['max_debt'] = max(0, int(((eV_1230 + eV_2110 * K1 * K2) - 0) / 12 * 0.6))
                    if eV_2110 > 0:
                        result['cred_day'] = int(((eV_1520 + eV_1520) / 2) / eV_2110 * 365)
                    result['equity'] = eV_1600 - (eV_1400 + eV_1500)

        return result
    except Exception as e:
        result['status'] = f'Error: {str(e)}'
        return result


# ============================================================================
# 8. СКОРИНГ
# ============================================================================
def calculate_lot_scores(df_all, lot_idx, lots_count):
    df = df_all.copy()
    df['lot_price'] = df['lots_prices'].apply(
        lambda prices: prices[lot_idx] if lot_idx < len(prices) else 0
    )
    df = df[df['lot_price'] > 0].reset_index(drop=True)

    if df.empty:
        return df

    df['score'] = 0
    df['score_details'] = [[] for _ in range(len(df))]

    df['revenue_ratio'] = df.apply(
        lambda r: (r['price_total'] / r['revenue'] * 100) if r['revenue'] > 0 else 999,
        axis=1
    )
    s = df['revenue_ratio'].sort_values().index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 2
        df.loc[s[0], 'score_details'].append("Доля тендера к выручке: +2")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 1
        df.loc[s[1], 'score_details'].append("Доля тендера к выручке: +1")

    s = df['max_debt'].sort_values(ascending=False).index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 2
        df.loc[s[0], 'score_details'].append("Наибольший аванс: +2")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 1
        df.loc[s[1], 'score_details'].append("Наибольший аванс: +1")

    df['advance_excess'] = df.apply(
        lambda r: (r['max_debt'] / (r['price_total'] * 0.1) * 100) if r['price_total'] > 0 else 0,
        axis=1
    )
    s = df['advance_excess'].sort_values(ascending=False).index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 2
        df.loc[s[0], 'score_details'].append("Превышение аванса к 10%: +2")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 1
        df.loc[s[1], 'score_details'].append("Превышение аванса к 10%: +1")

    for idx, row in df.iterrows():
        if row['yellow_statements'] == 0 and row['red_statements'] == 0:
            df.loc[idx, 'score'] += 2
            df.loc[idx, 'score_details'].append("Нет рисковых записей: +2")

    s = df['employees'].sort_values(ascending=False).index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 2
        df.loc[s[0], 'score_details'].append("Наибольший штат: +2")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 1
        df.loc[s[1], 'score_details'].append("Наибольший штат: +1")

    s = df['scoring_score'].sort_values(ascending=False).index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 2
        df.loc[s[0], 'score_details'].append("Наилучший скоринг: +2")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 1
        df.loc[s[1], 'score_details'].append("Наилучший скоринг: +1")

    df['cred_day_pos'] = df['cred_day'].apply(lambda x: x if x > 0 else 9999)
    s = df['cred_day_pos'].sort_values().index.tolist()
    valid = [i for i in s if df.loc[i, 'cred_day_pos'] < 9999]
    if len(valid) >= 1:
        df.loc[valid[0], 'score'] += 2
        df.loc[valid[0], 'score_details'].append("Наименьшая оборачиваемость: +2")
    if len(valid) >= 2:
        df.loc[valid[1], 'score'] += 1
        df.loc[valid[1], 'score_details'].append("Наименьшая оборачиваемость: +1")

    s = df['equity'].sort_values(ascending=False).index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 2
        df.loc[s[0], 'score_details'].append("Наибольшие чистые активы: +2")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 1
        df.loc[s[1], 'score_details'].append("Наибольшие чистые активы: +1")

    s = df['lot_price'].sort_values().index.tolist()
    if len(s) >= 1:
        df.loc[s[0], 'score'] += 6
        df.loc[s[0], 'score_details'].append("Наименьшая цена по лоту: +6")
    if len(s) >= 2:
        df.loc[s[1], 'score'] += 3
        df.loc[s[1], 'score_details'].append("Наименьшая цена по лоту: +3")

    df = df.sort_values('score', ascending=False).reset_index(drop=True)
    return df


def render_card(row, position_label, css_class, badge_class, lot_idx, lots_count):
    risk_html = ""
    if row['risk_text']:
        risks_joined = '<br>'.join(row['risk_text'][:10])
        risk_html = (
            f'<div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid {LIGHT_GRAY};">'
            f'<div style="font-size: 12px; color: {GRAY}; text-transform: uppercase; margin-bottom: 6px;">Рисковые записи</div>'
            f'<div style="font-size: 14px; color: {DARK}; line-height: 1.5;">{risks_joined}</div>'
            f'</div>'
        )

    lot_price = row['lots_prices'][lot_idx] if lot_idx < len(row['lots_prices']) else 0
    details_text = ' | '.join(row['score_details']) if row['score_details'] else 'Нет начислений'

    html = (
        f'<div class="results-card {css_class}">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">'
        f'<div>'
        f'<div class="company-name">{position_label} {row["name"]}</div>'
        f'<div class="company-inn">ИНН {row["inn"]}</div>'
        f'</div>'
        f'<div class="score-badge {badge_class}">Баллы: {row["score"]}</div>'
        f'</div>'
        f'<div class="result-grid">'
        f'<div class="result-item"><div class="label">Цена по лоту {lot_idx + 1}</div>'
        f'<div class="value">{lot_price:,.0f} ₽</div></div>'
        f'<div class="result-item"><div class="label">Сумма по всем лотам</div>'
        f'<div class="value">{row["price_total"]:,.0f} ₽</div></div>'
        f'<div class="result-item"><div class="label">Выручка (посл. период)</div>'
        f'<div class="value">{row["revenue"]:,.0f} ₽</div></div>'
        f'<div class="result-item"><div class="label">Сумма допустимого аванса</div>'
        f'<div class="value">{row["max_debt"]:,.0f} ₽</div></div>'
        f'<div class="result-item"><div class="label">Оборачиваемость</div>'
        f'<div class="value">{row["cred_day"]} дн.</div></div>'
        f'<div class="result-item"><div class="label">Чистые активы</div>'
        f'<div class="value">{row["equity"]:,.0f} ₽</div></div>'
        f'<div class="result-item"><div class="label">Скоринг (сумма) / Штат</div>'
        f'<div class="value">{row["scoring_score"]} / {row["employees"]} чел.</div></div>'
        f'</div>'
        f'<div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid {LIGHT_GRAY};">'
        f'<strong>Детализация баллов:</strong><br>'
        f'<span style="font-size: 14px; color: #4a4a4a;">{details_text}</span>'
        f'</div>'
        f'{risk_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ============================================================================
# 9. UI: ЗАГРУЗКА ФАЙЛА
# ============================================================================
st.markdown('<div class="search-card">', unsafe_allow_html=True)
st.markdown("### 📥 Загрузка сводной таблицы предложений")
st.markdown(
    "Загрузите Excel-файл «Сводная оценочная таблица» или «Конкурентный лист». "
    "Участники, ИНН и цены по лотам определяются автоматически."
)

uploaded = st.file_uploader(
    "Выберите файл .xlsx",
    type=["xlsx", "xls"],
    key="tender_file_uploader"
)

if uploaded is not None:
    if st.button("📊 Разобрать таблицу", type="primary", key="parse_excel_btn"):
        try:
            parsed = parse_tender_excel(uploaded)
            st.session_state.parsed = parsed
            st.session_state.analysis_result = None
            st.success(
                f"✅ Разобрано: {len(parsed['participants'])} участников, "
                f"{len(parsed['lots'])} лотов"
            )
            st.rerun()
        except Exception as e:
            st.error(f"❌ Ошибка разбора файла: {e}")

# Показываем сводку по загруженному файлу
if st.session_state.parsed is not None:
    parsed = st.session_state.parsed
    st.markdown(
        f"<div style='margin-top: 12px; color: {DARK};'>"
        f"<b>Загружено:</b> {len(parsed['participants'])} участников, "
        f"{len(parsed['lots'])} лотов</div>",
        unsafe_allow_html=True
    )
    with st.expander("👥 Список участников", expanded=False):
        for i, p in enumerate(parsed['participants'], 1):
            st.write(f"{i}. **{p['name'] or '—'}** — ИНН `{p['inn']}`")
    with st.expander("🧩 Список лотов", expanded=False):
        for i, lot in enumerate(parsed['lots'], 1):
            st.write(f"{i}. {lot}")

st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# 10. КНОПКА ЗАПУСКА ПРОВЕРКИ
# ============================================================================
if st.session_state.parsed is not None:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    st.markdown("### 🚀 Запуск проверки")
    st.markdown(
        "Будут запрошены данные из Контур.Фокуса по каждому участнику "
        "и построен рейтинг по каждому лоту."
    )

    if not api_key:
        st.error("❌ API ключ Контур.Фокуса не настроен")
    else:
        if st.button("🔍 Проверить участников и построить рейтинг",
                     type="primary", key="run_check_btn"):
            st.session_state.run_analysis = True
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# 11. АНАЛИЗ
# ============================================================================
if st.session_state.run_analysis:
    st.session_state.run_analysis = False
    parsed = st.session_state.parsed

    with st.spinner("Запрос данных из Контур.Фокуса..."):
        rows = []
        for p in parsed["participants"]:
            data = fetch_kontur_data(p["inn"], api_key)
            # Перезаписываем имя, если API вернул "Неизвестно"
            if not data.get("name") or data["name"] == "Неизвестно":
                data["name"] = p["name"] or "Неизвестно"
            data["lots_prices"] = [float(p["prices"].get(lot, 0.0) or 0.0)
                                   for lot in parsed["lots"]]
            data["price_total"] = sum(data["lots_prices"])
            rows.append(data)

        st.session_state.analysis_result = pd.DataFrame(rows)


# ============================================================================
# 12. РЕЗУЛЬТАТЫ
# ============================================================================
if st.session_state.analysis_result is not None and st.session_state.parsed is not None:
    df_all = st.session_state.analysis_result
    lot_titles = st.session_state.parsed["lots"]
    lots_count = len(lot_titles)

    st.markdown("---")
    st.markdown("## 📊 Результаты по лотам")

    # --- PDF ---
    col_pdf, _ = st.columns([1, 2])
    with col_pdf:
        try:
            pdf_buf = build_pdf_report(df_all, lots_count, lot_titles)
            st.download_button(
                label="📄 Скачать отчёт по тендеру (PDF)",
                data=pdf_buf,
                file_name=f"tender_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="download_pdf"
            )
        except Exception as e:
            st.error(f"Не удалось собрать PDF: {e}")

    # --- Сводная таблица по всем лотам ---
    st.markdown("### 📋 Сводная таблица: ИНН × Лоты (суммы, ₽)")
    summary = pd.DataFrame({
        "ИНН": [p["inn"] for p in st.session_state.parsed["participants"]],
        "Компания": [p["name"] for p in st.session_state.parsed["participants"]],
    })
    for lot in lot_titles:
        col_name = lot if len(lot) <= 40 else lot[:38] + "…"
        summary[col_name] = [
            float(p["prices"].get(lot, 0.0) or 0.0)
            for p in st.session_state.parsed["participants"]
        ]
    summary["Итого"] = summary[ [c for c in summary.columns
                                 if c not in ("ИНН", "Компания")] ].sum(axis=1)

    st.dataframe(
        summary.style.format({c: "{:,.0f}" for c in summary.columns
                              if c not in ("ИНН", "Компания")}),
        use_container_width=True, hide_index=True
    )

    # --- Результаты по каждому лоту ---
    for lot_idx, lot_title in enumerate(lot_titles):
        st.markdown(
            f'<div class="lot-header">🧩 {lot_title}</div>',
            unsafe_allow_html=True
        )

        df_lot = calculate_lot_scores(df_all, lot_idx, lots_count)

        if df_lot.empty:
            st.info(f"На лот «{lot_title}» не подано ни одной заявки.")
            continue

        display_cols = ['name', 'inn', 'lot_price', 'price_total', 'revenue',
                        'employees', 'scoring_score', 'max_debt', 'cred_day',
                        'equity', 'yellow_statements', 'red_statements', 'score']
        display_df = df_lot[display_cols].copy()
        display_df.columns = ['Компания', 'ИНН', 'Цена по лоту', 'Сумма по лотам',
                              'Выручка', 'Штат', 'Скоринг (сумма)', 'Аванс',
                              'Оборач.', 'Чистые активы', 'Жёлтых', 'Красных', 'Баллы']

        st.dataframe(display_df.style.format({
            'Цена по лоту': '{:,.0f}', 'Сумма по лотам': '{:,.0f}',
            'Выручка': '{:,.0f}', 'Аванс': '{:,.0f}', 'Чистые активы': '{:,.0f}'
        }), use_container_width=True, hide_index=True)

        winner = df_lot.iloc[0]
        render_card(winner, "🏆", "winner-card", "", lot_idx, lots_count)

        if len(df_lot) > 1:
            reserve = df_lot.iloc[1]
            render_card(reserve, "🔄", "reserve-card", "reserve", lot_idx, lots_count)

        if len(df_lot) > 2:
            with st.expander(f"Остальные участники лота «{lot_title}»"):
                for idx in range(2, len(df_lot)):
                    row = df_lot.iloc[idx]
                    render_card(row, f"#{idx + 1}", "other-card", "other",
                                lot_idx, lots_count)


# ============================================================================
# 13. ПОДВАЛ
# ============================================================================
st.markdown("""
<div class="footer">
    © 2026 Брусника · Проверка контрагентов
</div>
""", unsafe_allow_html=True)
