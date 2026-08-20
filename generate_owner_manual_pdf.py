import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Register Fonts supporting Cyrillic
font_paths = {
    'Arial': '/System/Library/Fonts/Supplemental/Arial.ttf',
    'Arial-Bold': '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    'Arial-Italic': '/System/Library/Fonts/Supplemental/Arial Italic.ttf',
    'Arial-BoldItalic': '/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf',
}

for name, path in font_paths.items():
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))

# Numbered Canvas
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Arial", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 752, "EVIDENCE DUE DILIGENCE — ПОСІБНИК ОУНЕРА ПРОЄКТУ")
            self.drawRightString(558, 752, "Adaptive Ontological Search 2.1 Core")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 744, 558, 744)
            
        # Running Footer
        page_text = f"Сторінка {self._pageNumber} з {page_count}"
        self.drawRightString(558, 34, page_text)
        self.drawString(54, 34, "КОНФІДЕНЦІЙНО — ДЛЯ ВНУТРІШНЬОГО ВИКОРИСТАННЯ ОУНЕРОМ ТА КОМАНДОЮ")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 46, 558, 46)
        
        self.restoreState()


def build_owner_manual_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    # Theme Palette
    C_PRIMARY = colors.HexColor("#0F172A")     # Dark Slate
    C_SECONDARY = colors.HexColor("#2563EB")   # Royal Blue
    C_ACCENT = colors.HexColor("#0D9488")      # Teal Accent
    C_TEXT = colors.HexColor("#1E293B")        # Charcoal Text
    C_MUTED = colors.HexColor("#64748B")       # Muted Gray
    C_BG_CARD = colors.HexColor("#F8FAFC")     # Light Card BG
    C_BG_BOX = colors.HexColor("#EFF6FF")      # Light Blue Box
    C_BORDER = colors.HexColor("#CBD5E1")      # Border Gray
    C_CODE_BG = colors.HexColor("#0F172A")     # Dark Terminal BG

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Arial-Bold',
        fontSize=18,
        leading=22,
        textColor=C_PRIMARY,
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Arial-Bold',
        fontSize=10.5,
        leading=14,
        textColor=C_SECONDARY,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        fontName='Arial-Bold',
        fontSize=12,
        leading=16,
        textColor=C_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        fontName='Arial-Bold',
        fontSize=9.5,
        leading=13,
        textColor=C_SECONDARY,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyMain',
        fontName='Arial',
        fontSize=8.5,
        leading=12,
        textColor=C_TEXT,
        spaceAfter=5
    )

    code_style = ParagraphStyle(
        'CodeBlock',
        fontName='Arial-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#38BDF8"),
        backColor=C_CODE_BG,
        leftIndent=8,
        rightIndent=8,
        borderPadding=5,
        spaceBefore=4,
        spaceAfter=6
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Arial-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=0
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Arial',
        fontSize=7.5,
        leading=10.5,
        textColor=C_TEXT
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        fontName='Arial-Bold',
        fontSize=8,
        leading=11,
        textColor=C_PRIMARY
    )

    table_cell_code = ParagraphStyle(
        'TableCellCode',
        fontName='Arial',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0369A1")
    )

    story = []

    # 1. HEADER & META BANNER
    story.append(Paragraph("EVIDENCE DUE DILIGENCE PLATFORM", title_style))
    story.append(Paragraph("Повний посібник оунера: Архітектура, Експлуатація та Запуск", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_SECONDARY, spaceBefore=2, spaceAfter=8))

    # Meta Info Card
    meta_data = [
        [
            Paragraph("<b>Версія рушія:</b> Ontological Search 2.1 Core", body_style),
            Paragraph("<b>Інтерфейси:</b> Web Dashboard | Telegram Bot | REST API", body_style)
        ],
        [
            Paragraph("<b>Методологія:</b> Richards Heuer ACH + AutoSchemaKG", body_style),
            Paragraph("<b>Призначення:</b> VC & Institutional Startup Audit", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[250, 254])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_BG_CARD),
        ('BOX', (0, 0), (-1, -1), 0.75, C_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # 2. SECTION 1: АРХІТЕКТУРА ТА ЯК ПРАЦЮЄ СЕРВІС
    story.append(Paragraph("1. Архітектура та принцип роботи сервісу", h1_style))
    story.append(Paragraph(
        "Платформа <b>Evidence Due Diligence</b> — це автономна агентна система для інституційного аудиту стартапів. "
        "На відміну від звичайного веб-пошуку або стандартних LLM-узагальнень, сервіс реалізує науковий підхід "
        "<b>Аналізу конкуруючих гіпотез (Richards Heuer ACH)</b> з обов'язковою верифікацією першоджерел та активним пошуком спростувань.",
        body_style
    ))

    # Pipeline Steps Table
    pipeline_data = [
        [Paragraph("Фаза / Модуль", table_header_style), Paragraph("Що робить рушій", table_header_style), Paragraph("Результат для інвестора", table_header_style)],
        [
            Paragraph("<b>1. AutoSchemaKG</b>", table_cell_bold),
            Paragraph("Динамічно генерує онтологію предметної області (MilTech, DeepTech, Fusion, BioMed) без заздалегідь зашитих шаблонів.", table_cell_style),
            Paragraph("Повна карта сутностей, стек технологій та архітектурний профіль.", table_cell_style)
        ],
        [
            Paragraph("<b>2. Heuer ACH Engine</b>", table_cell_bold),
            Paragraph("Формулює та зважує конкуруючі гіпотези:<br/>• <b>H1:</b> Наявність захищеного IP-моату та стійкості.<br/>• <b>H2:</b> Ризик замінності COTS / API Wrapper.<br/>• <b>H0:</b> Технічні вузькі місця або фейк-трекшн.<br/>• <b>Risk Lenses (L):</b> Регуляторні та ланцюгові ризики.", table_cell_style),
            Paragraph("Матриця консистентності, усунення суб'єктивних упереджень інвестора.", table_cell_style)
        ],
        [
            Paragraph("<b>3. Skeptic Subagent</b>", table_cell_bold),
            Paragraph("Агент-скептик цілеспрямовано шукає спростовуючі докази (Disproving Evidence), судові позови, претензії до патентів та відтік клієнтів.", table_cell_style),
            Paragraph("Реєстр критичних Red Flags із зазначенням рівня загрози.", table_cell_style)
        ],
        [
            Paragraph("<b>4. Claimify Engine</b>", table_cell_bold),
            Paragraph("Розкладає сировинну інформацію на атомарні твердження, визначає їх первинність та об'єднує дублікати у висхідні кластери походження (Root Clusters).", table_cell_style),
            Paragraph("Захист від циркулярних цитувань та штучного завищення авторитету джерел.", table_cell_style)
        ],
        [
            Paragraph("<b>5. Safety Gates & Verdict</b>", table_cell_bold),
            Paragraph("Шлюзи безпеки блокують категоріальні рекомендації при недостатності даних. Розраховує фінальний <b>Conviction Score</b> (0.0–1.0).", table_cell_style),
            Paragraph("Фінальний інвестиційний вердикт: STRONG INVEST, CAUTION, DEEP AUDIT, PASS.", table_cell_style)
        ]
    ]

    p_table = Table(pipeline_data, colWidths=[105, 245, 154])
    p_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_BG_CARD]),
    ]))
    story.append(p_table)
    story.append(Spacer(1, 10))

    # 3. SECTION 2: ІНТЕРФЕЙСИ ТА СПОСОБИ ВИКОРИСТАННЯ
    story.append(Paragraph("2. Основні інтерфейси системи", h1_style))
    
    story.append(Paragraph("<b>[A] Telegram Бот (Режим Human-in-the-Loop)</b>", h2_style))
    story.append(Paragraph(
        "Бот працює як персональний Due Diligence аналітик з підтримкою черги підтвердження: "
        "коли клієнт надсилає посилання на стартап, запит надходить адміністратору з інлайн-кнопками схвалення. "
        "Після схвалення бот формує звіт і надсилає його клієнту у вигляді 3 структурованих частин (Executive Verdict, Red Flags & Tech Moat, Claimify Provenance & Founder Questions).",
        body_style
    ))

    story.append(Paragraph("<b>[B] Інтерактивний Web Dashboard</b>", h2_style))
    story.append(Paragraph(
        "Візуальна панель для інвестиційного комітету. Дозволяє перемикати стартапи (Pacific Fusion, Helsing, Lensa AI тощо), "
        "переглядати граф понять AutoSchema, матрицю оцінки гіпотез, деталізацію Red Flags та експортовані звіти.",
        body_style
    ))

    story.append(Paragraph("<b>[C] REST API Сервер та CLI Runner</b>", h2_style))
    story.append(Paragraph(
        "Надає HTTP-ендпоінти (<code>/api/health</code>, <code>/api/reports</code>, <code>/api/analyze</code>) "
        "для програмної інтеграції та консольний скрипт <code>run_audit.py</code> для миттєвого аудиту з терміналу.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # 4. SECTION 3: ІНСТРУКЦІЯ З ЗАПУСКУ ТА КОМАНДИ В ТЕРМІНАЛІ
    story.append(Paragraph("3. Покрокова інструкція запуску (Термінал)", h1_style))
    story.append(Paragraph(
        "<b>Базове правило:</b> Перед виконанням команд обов'язково перейдіть у робочу директорію проєкту:",
        body_style
    ))
    story.append(Paragraph('cd "/Users/maksymkuzmenko/Documents/Antigravity Ontological Search"', code_style))

    # Launch Commands Table
    launch_data = [
        [Paragraph("Компонент", table_header_style), Paragraph("Команда для запуску", table_header_style), Paragraph("Опис та перевірка", table_header_style)],
        [
            Paragraph("<b>Telegram Bot</b>", table_cell_bold),
            Paragraph("<code>python3 bot.py</code><br/><i>або</i> <code>./start_bot.sh</code>", table_cell_code),
            Paragraph("Запускає long-polling бота. Бот слухає запити користувачів та адмінські кнопки схвалення.", table_cell_style)
        ],
        [
            Paragraph("<b>Web Dashboard</b>", table_cell_bold),
            Paragraph("<code>python3 -m http.server 3000 -d web</code>", table_cell_code),
            Paragraph("Запускає локальний веб-сервер. Інтерфейс доступний за адресою: <b>http://localhost:3000</b>", table_cell_style)
        ],
        [
            Paragraph("<b>REST API Server</b>", table_cell_bold),
            Paragraph("<code>python3 server.py 8080</code>", table_cell_code),
            Paragraph("Запускає асинхронний бекенд на порті 8080. Ендпоінт здоров'я: <b>/api/health</b>", table_cell_style)
        ],
        [
            Paragraph("<b>CLI Audit Runner</b>", table_cell_bold),
            Paragraph("<code>python3 run_audit.py \"Target\" \"Category\"</code>", table_cell_code),
            Paragraph("Проводить повний аудит в терміналі та зберігає результат у <code>showcase_reports.json</code>.", table_cell_style)
        ],
        [
            Paragraph("<b>Unit Test Suite</b>", table_cell_bold),
            Paragraph("<code>python3 -m unittest discover tests</code>", table_cell_code),
            Paragraph("Перевіряє роботу ACH-матриці, шлюзів безпеки та дедуплікації джерел.", table_cell_style)
        ]
    ]

    l_table = Table(launch_data, colWidths=[105, 220, 179])
    l_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_BG_CARD]),
    ]))
    story.append(l_table)
    story.append(Spacer(1, 10))

    # 5. SECTION 4: КОНФІГУРАЦІЯ ТА ВАЖЛИВІ ФАЙЛИ
    story.append(Paragraph("4. Карта конфігураційних файлів", h1_style))

    files_data = [
        [Paragraph("Файл / Шлях", table_header_style), Paragraph("Призначення", table_header_style), Paragraph("Параметри конфігурації", table_header_style)],
        [
            Paragraph("<code>bot_config.json</code>", table_cell_code),
            Paragraph("Конфігурація Telegram-бота", table_cell_style),
            Paragraph("<code>token</code>, <code>admin_chat_id</code>", table_cell_style)
        ],
        [
            Paragraph("<code>web/public/data/...</code>", table_cell_code),
            Paragraph("Сховище згенерованих звітів", table_cell_style),
            Paragraph("<code>showcase_reports.json</code> — JSON-масив усіх звітів.", table_cell_style)
        ],
        [
            Paragraph("<code>.agents/.../config.py</code>", table_cell_code),
            Paragraph("Конфігурація моделей Gemini", table_cell_style),
            Paragraph("<code>DEFAULT_PRO_MODEL</code>, <code>DEFAULT_FLASH_MODEL</code>", table_cell_style)
        ],
        [
            Paragraph("<code>web/netlify.toml</code>", table_cell_code),
            Paragraph("Конфігурація хмарного деплою", table_cell_style),
            Paragraph("Налаштування публікації веб-інтерфейсу на Netlify.", table_cell_style)
        ]
    ]

    f_table = Table(files_data, colWidths=[130, 160, 214])
    f_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_BG_CARD]),
    ]))
    story.append(f_table)
    story.append(Spacer(1, 10))

    # Final Notice Box
    story.append(Paragraph(
        "<b>Порада оунеру:</b> Для регулярної роботи рекомендується тримати Telegram-бот запущеним у фоновому режимі "
        "або на хмарному сервері (Railway / Modal), а результати переглядати через підключений Web Dashboard.",
        body_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {output_path}")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "Evidence_Due_Diligence_Owner_Manual.pdf")
    build_owner_manual_pdf(out)
