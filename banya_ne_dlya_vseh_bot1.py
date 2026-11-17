import asyncio
import json
import logging
import os
import re
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ============================================================
# НАСТРОЙКИ
# ============================================================
# Вставьте сюда НОВЫЙ токен, полученный после перевыпуска в @BotFather.
BOT_TOKEN = os.getenv("BOT_TOKEN", "9111022487:AAG8yOlVZxCbjaMMzY1WmgST_4dDIuDwiPI")

# Telegram ID администратора, указанный владельцем бота.
ADMIN_ID = 743150720

DB_NAME = "banya_applications.db"
logging.basicConfig(level=logging.INFO)


# ============================================================
# АНКЕТА
# Ответы сохраняются последовательно в SQLite.
# ============================================================
QUESTIONS = [
    ("Как вас зовут?", "text"),
    ("Чем вы занимаетесь в жизни? Расскажите немного о себе.", "text"),
    ("Откуда вы узнали о БАНЕ НЕ ДЛЯ ВСЕХ?", "choice",
     ["От действующего участника", "От основателя или организатора",
      "Из социальных сетей", "От знакомых", "Другое"]),
    ("Если вас пригласил действующий участник, укажите его имя. Если нет — напишите «Нет».", "text"),
    ("Что именно привлекло вас в БАНЕ НЕ ДЛЯ ВСЕХ?", "text"),
    ("Почему вы хотите стать частью закрытого сообщества, а не просто посетить отдельную банную или SPA-процедуру?", "text"),
    ("Что вам хотелось бы получить от участия в сообществе? Что вы хотели бы прожить или открыть в себе?", "text"),
    ("Чего вам сейчас больше всего не хватает в обычной социальной жизни, отношениях или общении с окружающими?", "text"),
    ("Что вы сами готовы привнести в сообщество и дать другим участникам?", "text"),
    ("Насколько вам комфортно принимать прикосновения, массаж или другую телесную заботу от других участников? Есть ли у вас определённые условия или ограничения? Не указывайте диагнозы и лишние медицинские подробности — достаточно описать важные для безопасности ограничения.", "text"),
    ("Насколько вам комфортно самостоятельно проявлять телесную заботу к другому человеку (массировать, парить, прикасаться с его согласия)?", "text"),
    ("Как вы относитесь к нахождению в одном пространстве с обнажёнными людьми разного пола во время банных практик?", "text"),
    ("Как вы понимаете разницу между обнажённостью, телесным контактом и сексуальным взаимодействием?", "text"),
    ("Готовы ли вы перед любым прикосновением спрашивать разрешение и спокойно принимать отказ, даже если сами хотите проявить заботу?", "choice", ["Да", "Нет", "Хочу уточнить условия"]),
    ("Насколько вам комфортно говорить «нет», если какое-либо прикосновение, предложение или взаимодействие вам неприятно?", "text"),
    ("Как вы поступите, если другой участник откажется от вашего прикосновения или не захочет взаимодействовать с вами?", "text"),
    ("Что вы будете делать, если во время групповой практики почувствуете дискомфорт или увидите, что кому-то из участников некомфортно?", "text"),
    ("Представьте, что вам понравился другой участник сообщества, но взаимного интереса нет. Как вы будете вести себя дальше?", "text"),
    ("Рассматриваете ли вы БАНЮ НЕ ДЛЯ ВСЕХ как место для поиска романтического или сексуального партнёра? Если да, расскажите подробнее о своих ожиданиях.", "text"),
    ("Что для вас абсолютно недопустимо в общении и взаимодействии между участниками сообщества?", "text"),
    ("Был ли у вас ранее опыт телесных практик, банных ритуалов, групповых взаимодействий или подобных сообществ? Если да, расскажите о своих впечатлениях.", "text"),
    ("Насколько для вас важно соблюдать конфиденциальность? Готовы ли вы не выносить личные истории, разговоры и подробности взаимодействия участников за пределы сообщества без их разрешения?", "text"),
    ("Готовы ли вы соблюдать правила сообщества, уважать индивидуальные границы участников, участвовать в предварительном отборе и принимать финансовые условия участия?", "text"),
    ("Есть ли что-то ещё, что нам важно знать о вас? Почему, на ваш взгляд, именно вы могли бы стать хорошей частью БАНИ НЕ ДЛЯ ВСЕХ?", "text"),
]

FORM_CONFIRMATIONS = [
    "Я понимаю формат сообщества и осознанно хочу познакомиться с ним.",
    "Я понимаю, что обнажённость не означает согласия на прикосновения.",
    "Я уважаю личные границы других людей и не допускаю давления на участников.",
    "Я понимаю, что любое телесное взаимодействие возможно исключительно по взаимному согласию.",
    "Я готов(а) соблюдать конфиденциальность.",
    "Я понимаю, что могу отказаться от любой практики или остановить своё участие в любой момент.",
    "Я готов(а) соблюдать общие правила сообщества.",
    "Я понимаю, что заполнение анкеты не гарантирует вступление в сообщество.",
]

# Кодекс разбит на 10 разделов. После каждого раздела кандидат подтверждает согласие.
CODEX_SECTIONS = [
"""БАНЯ НЕ ДЛЯ ВСЕХ
Кодекс сообщества
Культура, правила и границы

1. НАШИ ЦЕННОСТИ
БАНЯ НЕ ДЛЯ ВСЕХ — закрытое сообщество людей, объединённых интересом к самопознанию, телесным практикам, взаимной заботе, доверию и искреннему человеческому взаимодействию.

Мы создаём пространство, где можно расслабиться, снять привычные социальные роли, перестать соответствовать чужим ожиданиям и быть собой.

Здесь не нужно ничего доказывать, заслуживать внимание или сравнивать себя с другими.

Мы учимся:
- быть внимательными к себе и окружающим;
- проявлять заботу и принимать её;
- чувствовать свои желания и уважать свои ограничения;
- доверять, не нарушая чужих границ;
- быть открытыми без необходимости переходить личные границы;
- принимать различия между людьми без осуждения;
- создавать атмосферу, в которой каждый может чувствовать себя спокойно и свободно.""",
"""2. КУЛЬТУРА ПРОСТРАНСТВА
Главная идея сообщества: свобода одного человека заканчивается там, где начинается нарушение границ другого.

Мы придерживаемся принципов:

Уважение — каждый человек достоин уважительного отношения независимо от пола, возраста, внешности, социального положения, профессии, семейного статуса и личных взглядов.

Равенство — здесь нет людей первого и второго сорта. Мы не делим участников на более привлекательных, интересных, важных или значимых.

Взаимность — мы не приходим только получать внимание, заботу и удовольствие. Каждый участник становится частью общего пространства и вносит свой вклад в него.

Искренность — мы ценим открытость, честность и способность говорить о чувствах, желаниях и ограничениях без манипуляций и давления.

Бережность — у каждого свой опыт, чувствительность, темп сближения и уровень доверия.

Свобода проявления — каждый вправе быть собой, но не вправе использовать собственную свободу как оправдание нарушения чужих границ.""",
"""3. КОНФИДЕНЦИАЛЬНОСТЬ
Доверие возможно только при уважении к личному пространству каждого.

Личные истории, переживания и разговоры участников остаются внутри сообщества.

Запрещено передавать посторонним личную информацию о других участниках без их разрешения.

Фото-, видеосъёмка и запись разговоров возможны только с предварительного согласия всех, кто попадает в запись.

Публиковать материалы с участием других людей можно только с их отдельного согласия.

Запрещено распространять слухи, обсуждать чужую личную жизнь и использовать полученную информацию для давления или манипуляций.

Конфиденциальность не распространяется на сокрытие реальной угрозы безопасности человека. В таких ситуациях Хранитель пространства вправе передать необходимую информацию тем, кто может помочь.""",
"""4. ТЕЛЕСНОСТЬ И ПРИКОСНОВЕНИЯ
Телесная забота является одной из важных составляющих сообщества. Участники могут парить друг друга, делать массаж, проявлять внимание через прикосновения и участвовать в телесных практиках.

Перед прикосновением необходимо получить согласие человека. Это касается массажа, парения, поглаживаний, объятий и любых других форм физического контакта.

Согласие на одно действие не означает согласия на другое.

Согласие можно изменить или отозвать в любой момент.

Молчание, улыбка, отсутствие сопротивления или предыдущий опыт взаимодействия не являются согласием.

Каждый участник имеет право отказаться от любого прикосновения без объяснения причин.

Нельзя настаивать, уговаривать, переубеждать или обижаться на отказ.

Нельзя самостоятельно инициировать телесный контакт, проверять границы другого человека или использовать практики как способ сближения без его согласия.

Если человек говорит «нет», «не хочу», «не сейчас» или демонстрирует дискомфорт, взаимодействие необходимо немедленно прекратить.

Обнажённость в банном пространстве является естественной частью некоторых практик, но никогда не означает сексуальной доступности или разрешения на прикосновения.

Запрещены сексуализированные комментарии, нежелательные прикосновения, домогательства и любые действия, которые могут восприниматься как нарушение личных границ.

Мы не оцениваем тела друг друга, не сравниваем и не превращаем телесную открытость в повод для сексуального внимания.""",
"""5. ВЗАИМОДЕЙСТВИЕ МЕЖДУ УЧАСТНИКАМИ
В нашем сообществе нет задачи знакомиться ради романтических или сексуальных отношений. Мы объединяемся ради опыта человеческого взаимодействия, заботы, доверия, общения и самопознания.

Не следует воспринимать доброжелательность, заботу или участие в практике как проявление романтического интереса.

Нельзя использовать встречи и телесные практики для поиска интимной близости.

Симпатия не даёт права ожидать взаимности или добиваться внимания человека.

Отказ необходимо принимать спокойно, без давления и изменения отношения к человеку.

Каждый участник имеет равное право на уважение и комфорт.""",
"""6. ОБЩЕНИЕ И ПОВЕДЕНИЕ
Мы создаём атмосферу, в которой можно говорить открыто или сохранять молчание, делиться личным или оставлять что-то при себе.

Недопустимы:
- осуждение, насмешки и обесценивание;
- навязывание взглядов, советов и жизненных принципов;
- использование чужой откровенности против человека;
- манипуляции, провокации и публичные выяснения отношений;
- навязчивое общение, объятия, прикосновения и предложения личных встреч;
- давление на человека, который не хочет продолжать взаимодействие.

Мы стараемся слушать, а не оценивать. Поддерживать, а не исправлять. Интересоваться, а не вторгаться.

Каждый имеет право говорить или молчать, делиться личным или оставлять что-то при себе.""",
"""7. ТРЕЗВОСТЬ И БЕЗОПАСНОСТЬ
Безопасность каждого участника важнее любой практики или программы встречи.

Участие возможно только в трезвом состоянии.

Запрещено приносить и употреблять алкоголь и другие психоактивные вещества во время встреч.

Каждый должен ответственно относиться к своему физическому состоянию и заранее сообщать Хранителю пространства о значимых противопоказаниях и ограничениях, которые могут повлиять на безопасность практик.

Нельзя самостоятельно проводить практики за пределами согласованного формата и своей компетенции.

Никого нельзя принуждать к участию в практике.

Каждый вправе остановить практику или обратиться за помощью в любой момент.

Если кому-то стало плохо или человек чувствует себя небезопасно, необходимо сообщить Хранителю пространства.

Агрессия, угрозы, физическое давление и любые формы насилия недопустимы.""",
"""8. ОТВЕТСТВЕННОСТЬ УЧАСТНИКОВ
Каждый участник принимает ответственность за атмосферу и безопасность сообщества.

Это означает: 
- уважать чужие границы, даже если лично вы привыкли к другому формату общения;
- не ставить собственные желания выше комфорта других;
- отвечать за свои слова и поступки;
- спокойно принимать отказы;
- соблюдать общие правила и уважать решения, направленные на безопасность пространства;
- не создавать ситуаций, в которых другим приходится оправдываться за свои личные границы.""",
"""9. СОХРАНЕНИЕ ГРАНИЦ СООБЩЕСТВА
Хранитель пространства следит за соблюдением Кодекса и сохранением безопасной атмосферы.

При нарушении правил могут применяться следующие меры:
- личный разговор и предупреждение;
- остановка участия человека в конкретной практике или встрече;
- прекращение участия в сообществе при серьёзных или повторных нарушениях.

При домогательствах, агрессии, нарушении конфиденциальности и других серьёзных нарушениях границ участие человека может быть прекращено без предварительных предупреждений.

Каждый участник вправе отказаться от взаимодействия с человеком, рядом с которым чувствует себя небезопасно.""",
"""10. НАШЕ ОБЩЕЕ СОГЛАШЕНИЕ
Становясь частью БАНИ НЕ ДЛЯ ВСЕХ, я подтверждаю, что:
1) Я прочитал(а) и принимаю Кодекс сообщества.
2) Я обязуюсь соблюдать конфиденциальность.
3) Я не буду фотографировать, снимать или записывать других без их согласия.
4) Я понимаю, что любые прикосновения возможны только по взаимному согласию.
5) Я уважаю право каждого отказаться от практики или прекратить взаимодействие.
6) Я обязуюсь принимать отказ спокойно и без давления.
7) Я буду посещать встречи только в трезвом состоянии.
8) Я не буду использовать сообщество для поиска сексуальных контактов или удовлетворения своих ожиданий за счёт других.
9) Я обязуюсь уважать личные и физические границы участников.
10) Я понимаю, что безопасность и атмосфера пространства зависят от каждого из нас.
11) Я понимаю, что нарушение Кодекса может стать основанием для прекращения моего участия в сообществе.

Подтверждая согласие с Кодексом, я принимаю не только правила, но и ценности БАНИ НЕ ДЛЯ ВСЕХ.

Здесь можно быть открытым, но нельзя быть бесцеремонным.

Здесь можно проявлять заботу, но нельзя навязывать её.

Здесь можно быть собой, но нельзя забывать о других.

Здесь можно доверять, но нельзя использовать чужое доверие.

Мы не обещаем, что каждый найдёт здесь ответы на все свои вопросы. Но мы создаём пространство, в котором каждый может получить новый опыт взаимодействия с собой и другими людьми.

Мы не просто собираемся вместе. Мы вместе создаём культуру, в которой человеку можно быть человеком."""
]

CODEX_CONFIRMATIONS = [
    "Я прочитал(а) и принимаю раздел 1 «Наши ценности».",
    "Я прочитал(а) и принимаю раздел 2 «Культура пространства».",
    "Я прочитал(а) и принимаю раздел 3 «Конфиденциальность».",
    "Я прочитал(а) и принимаю раздел 4 «Телесность и прикосновения».",
    "Я прочитал(а) и принимаю раздел 5 «Взаимодействие между участниками».",
    "Я прочитал(а) и принимаю раздел 6 «Общение и поведение».",
    "Я прочитал(а) и принимаю раздел 7 «Трезвость и безопасность».",
    "Я прочитал(а) и принимаю раздел 8 «Ответственность участников».",
    "Я прочитал(а) и принимаю раздел 9 «Сохранение границ сообщества».",
    "Я прочитал(а) и принимаю раздел 10 «Наше общее соглашение»."
]


# ============================================================
# БАЗА ДАННЫХ
# ============================================================
def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            step INTEGER NOT NULL DEFAULT 0,
            answers TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT
        )
        """)


def get_app(user_id):
    with db() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM applications WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def save_app(user_id, username, first_name, step, answers, status="in_progress"):
    with db() as con:
        con.execute("""
        INSERT INTO applications(user_id, username, first_name, step, answers, status, created_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
          username=excluded.username,
          first_name=excluded.first_name,
          step=excluded.step,
          answers=excluded.answers,
          status=excluded.status
        """, (user_id, username, first_name, step, json.dumps(answers, ensure_ascii=False),
              status, datetime.now().isoformat(timespec="minutes")))


def update_status(user_id, status):
    with db() as con:
        con.execute("UPDATE applications SET status=? WHERE user_id=?", (status, user_id))


def all_applications():
    with db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT user_id, first_name, username, status, created_at FROM applications ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# КЛАВИАТУРЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def choice_keyboard(options):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=x)] for x in options],
        resize_keyboard=True,
        one_time_keyboard=True
    )


YES_NO = ["Подтверждаю", "Не подтверждаю"]


async def send_long_message(bot, chat_id, text, reply_markup=None):
    # Telegram ограничивает длину одного сообщения примерно 4096 символами.
    chunks = []
    while len(text) > 3800:
        cut = text.rfind("\n", 0, 3800)
        if cut < 1000:
            cut = 3800
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    chunks.append(text)
    for i, chunk in enumerate(chunks):
        await bot.send_message(
            chat_id, chunk,
            reply_markup=reply_markup if i == len(chunks) - 1 else None
        )


async def ask_current_question(message: Message, app):
    step = app["step"]
    answers = json.loads(app["answers"])

    if 1 <= step <= len(QUESTIONS):
        question, kind, *rest = QUESTIONS[step - 1]
        await message.answer(f"Вопрос {step} из {len(QUESTIONS)}\n\n{question}",
                             reply_markup=choice_keyboard(rest[0]) if kind == "choice" else ReplyKeyboardRemove())
        return

    form_start = len(QUESTIONS) + 1
    form_end = form_start + len(FORM_CONFIRMATIONS) - 1
    if form_start <= step <= form_end:
        item = FORM_CONFIRMATIONS[step - form_start]
        await message.answer(
            f"Подтверждение {step - len(QUESTIONS)} из {len(FORM_CONFIRMATIONS)}\n\n{item}\n\nПодтверждаете?",
            reply_markup=choice_keyboard(YES_NO)
        )
        return

    codex_start = form_end + 1
    codex_end = codex_start + len(CODEX_SECTIONS) - 1
    if codex_start <= step <= codex_end:
        idx = step - codex_start
        await message.answer(
            f"Кодекс — раздел {idx + 1} из {len(CODEX_SECTIONS)}\n\n{CODEX_SECTIONS[idx]}"
        )
        await message.answer(
            f"Подтверждаете согласие с разделом {idx + 1} из {len(CODEX_SECTIONS)}?",
            reply_markup=choice_keyboard(YES_NO)
        )


async def finish_application(bot: Bot, user_id: int):
    app = get_app(user_id)
    answers = json.loads(app["answers"])
    update_status(user_id, "pending_admin")

    username = f"@{app['username']}" if app["username"] else "не указан"
    report = (
        "🆕 НОВАЯ ЗАЯВКА — БАНЯ НЕ ДЛЯ ВСЕХ\n\n"
        f"Имя в Telegram: {app['first_name']}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user_id}\n"
        f"Дата: {app['created_at']}\n\n"
        "ОТВЕТЫ АНКЕТЫ:\n"
    )
    for i, (question, *_rest) in enumerate(QUESTIONS, start=1):
        report += f"\n{i}. {question}\nОтвет: {answers.get(f'q{i}', '—')}\n"

    report += "\nПОДТВЕРЖДЕНИЯ АНКЕТЫ:\n"
    for i, item in enumerate(FORM_CONFIRMATIONS, start=1):
        report += f"{i}. {item} — {answers.get(f'form{i}', '—')}\n"

    report += "\nПОДТВЕРЖДЕНИЯ КОДЕКСА:\n"
    for i, item in enumerate(CODEX_CONFIRMATIONS, start=1):
        report += f"{i}. {item} — {answers.get(f'codex{i}', '—')}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить анкету", callback_data=f"approve:{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{user_id}")
        ]
    ])
    await send_long_message(bot, ADMIN_ID, report, reply_markup=keyboard)
    await bot.send_message(
        user_id,
        "Спасибо за заполнение анкеты и внимательное ознакомление с Кодексом.\n\n"
        "Ваша заявка передана Хранителю пространства. Это ещё не означает вступление в сообщество. "
        "Следующий этап — рассмотрение анкеты и, при предварительном одобрении, личное знакомство.\n\n"
        "Пожалуйста, ожидайте сообщения.",
        reply_markup=ReplyKeyboardRemove()
    )


# ============================================================
# ЗАПУСК И ОБРАБОТЧИКИ
# ============================================================
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    user = message.from_user
    old = get_app(user.id)

    if old and old["status"] in ("pending_admin", "preapproved", "invited", "rejected", "age_rejected"):
        await message.answer(
            "Ваша заявка уже находится в системе.\n"
            f"Текущий статус: {old['status']}.\n"
            "Если вы считаете, что это ошибка, свяжитесь с организатором."
        )
        return

    answers = {}
    save_app(user.id, user.username, user.first_name, 0, answers)
    await message.answer(
        "Добро пожаловать в «БАНЯ НЕ ДЛЯ ВСЕХ».\n\n"
        "Это закрытое сообщество для людей, которым интересны самопознание, телесные практики, "
        "банные ритуалы, забота, открытое общение и уважительное взаимодействие.\n\n"
        "Мы не стремимся собрать как можно больше людей. Нам важно сохранить атмосферу доверия, "
        "уважения и безопасности.\n\n"
        "Перед началом анкеты подтвердите, пожалуйста, что вам уже исполнилось 18 лет.\n"
        "Введите свой возраст цифрами."
    )


@dp.message(Command("cancel"))
async def cancel(message: Message):
    app = get_app(message.from_user.id)
    if app and app["status"] == "in_progress":
        update_status(message.from_user.id, "cancelled")
    await message.answer(
        "Заполнение остановлено. Если захотите начать заново, отправьте /start.",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Command("status"))
async def status(message: Message):
    app = get_app(message.from_user.id)
    if not app:
        await message.answer("Вы ещё не начинали заполнение анкеты. Отправьте /start.")
        return
    labels = {
        "in_progress": "анкета заполняется",
        "pending_admin": "заявка передана Хранителю на рассмотрение",
        "preapproved": "анкета предварительно одобрена; ожидается личное знакомство",
        "invited": "вам отправлено приглашение на первую встречу",
        "rejected": "заявка не одобрена",
        "age_rejected": "участие возможно только с 18 лет",
        "cancelled": "заполнение остановлено",
    }
    await message.answer("Статус вашей заявки: " + labels.get(app["status"], app["status"]))


@dp.message(Command("applications"))
async def admin_applications(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    rows = all_applications()
    if not rows:
        await message.answer("Заявок пока нет.")
        return
    lines = ["ЗАЯВКИ:"]
    for row in rows[:30]:
        uname = f"@{row['username']}" if row["username"] else "username нет"
        lines.append(f"ID {row['user_id']} | {row['first_name']} | {uname} | {row['status']}")
    await message.answer("\n".join(lines))


@dp.message()
async def handle_answer(message: Message, bot: Bot):
    if not message.from_user or not message.text:
        return
    user_id = message.from_user.id
    app = get_app(user_id)

    if not app or app["status"] != "in_progress":
        return

    text = message.text.strip()
    step = app["step"]
    answers = json.loads(app["answers"])

    # Первый шаг — возраст.
    if step == 0:
        match = re.search(r"\d{1,3}", text)
        if not match:
            await message.answer("Пожалуйста, введите возраст цифрами, например: 28.")
            return
        age = int(match.group())
        if age < 18:
            save_app(user_id, message.from_user.username, message.from_user.first_name,
                     0, {"age": age}, "age_rejected")
            await message.answer(
                "Спасибо за интерес к сообществу. Участие возможно только с 18 лет. "
                "Сейчас мы не можем продолжить оформление заявки.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        answers["age"] = str(age)
        save_app(user_id, message.from_user.username, message.from_user.first_name, 1, answers)
        await ask_current_question(message, get_app(user_id))
        return

    # Вопросы анкеты.
    if 1 <= step <= len(QUESTIONS):
        q_num = step
        q_text, q_type, *rest = QUESTIONS[q_num - 1]
        if q_type == "choice" and text not in rest[0]:
            await message.answer("Пожалуйста, выберите один из предложенных вариантов.")
            return
        if q_type == "age":
            age_match = re.search(r"\\d{1,3}", text)
            if not age_match:
                await message.answer("Пожалуйста, укажите возраст цифрами.")
                return
            confirmed_age = int(age_match.group())
            if confirmed_age < 18:
                update_status(user_id, "age_rejected")
                await message.answer(
                    "Участие возможно только с 18 лет. Мы не можем продолжить оформление заявки.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            answers["age"] = str(confirmed_age)
        answers[f"q{q_num}"] = text
        next_step = step + 1
        save_app(user_id, message.from_user.username, message.from_user.first_name, next_step, answers)
        await ask_current_question(message, get_app(user_id))
        return

    # Подтверждения анкеты.
    form_start = len(QUESTIONS) + 1
    form_end = form_start + len(FORM_CONFIRMATIONS) - 1
    if form_start <= step <= form_end:
        if text not in YES_NO:
            await message.answer("Выберите «Подтверждаю» или «Не подтверждаю».")
            return
        idx = step - form_start + 1
        if text != "Подтверждаю":
            update_status(user_id, "cancelled")
            await message.answer(
                "Без подтверждения всех обязательных положений мы не можем продолжить оформление заявки.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        answers[f"form{idx}"] = text
        next_step = step + 1
        save_app(user_id, message.from_user.username, message.from_user.first_name, next_step, answers)
        if next_step == form_end + 1:
            await message.answer(
                "Спасибо. Теперь внимательно ознакомьтесь с Кодексом сообщества. "
                "После каждого раздела бот попросит подтвердить согласие.",
                reply_markup=ReplyKeyboardRemove()
            )
        await ask_current_question(message, get_app(user_id))
        return

    # Подтверждения 10 разделов Кодекса.
    codex_start = form_end + 1
    codex_end = codex_start + len(CODEX_SECTIONS) - 1
    if codex_start <= step <= codex_end:
        if text not in YES_NO:
            await message.answer("Выберите «Подтверждаю» или «Не подтверждаю».")
            return
        idx = step - codex_start + 1
        if text != "Подтверждаю":
            update_status(user_id, "cancelled")
            await message.answer(
                "Спасибо за честный ответ. Без согласия со всеми разделами Кодекса "
                "мы не можем продолжить оформление заявки.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        answers[f"codex{idx}"] = text
        next_step = step + 1
        save_app(user_id, message.from_user.username, message.from_user.first_name, next_step, answers)
        if next_step <= codex_end:
            await ask_current_question(message, get_app(user_id))
        else:
            await finish_application(bot, user_id)
        return


@dp.callback_query(F.data.startswith("approve:"))
async def approve_application(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    app = get_app(user_id)
    if not app:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    update_status(user_id, "preapproved")
    await bot.send_message(
        user_id,
        "Ваша анкета предварительно одобрена.\n\n"
        "Следующий этап — личное знакомство с Хранителем пространства. "
        "Это ещё не является окончательным приглашением в сообщество. "
        "Организатор свяжется с вами отдельно."
    )
    invite_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎟 Отправить приглашение после знакомства",
                             callback_data=f"invite:{user_id}"),
        InlineKeyboardButton(text="Завершить рассмотрение",
                             callback_data=f"reject:{user_id}")
    ]])
    await callback.message.answer(
        f"Анкета {user_id} предварительно одобрена. После личного знакомства можно отправить приглашение.",
        reply_markup=invite_keyboard
    )
    await callback.answer("Анкета одобрена.")


@dp.callback_query(F.data.startswith("invite:"))
async def invite_application(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    app = get_app(user_id)
    if not app:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    update_status(user_id, "invited")
    await bot.send_message(
        user_id,
        "Вы прошли предварительный отбор и личное знакомство.\n\n"
        "Хранитель пространства приглашает вас на первую встречу сообщества «БАНЯ НЕ ДЛЯ ВСЕХ».\n\n"
        "Для согласования даты, времени и организационных деталей, пожалуйста, ответьте на это сообщение."
    )
    await callback.message.answer(f"Приглашение отправлено кандидату {user_id}.")
    await callback.answer("Приглашение отправлено.")


@dp.callback_query(F.data.startswith("reject:"))
async def reject_application(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    app = get_app(user_id)
    if not app:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    update_status(user_id, "rejected")
    await bot.send_message(
        user_id,
        "Спасибо за интерес к «БАНЕ НЕ ДЛЯ ВСЕХ» и время, которое вы уделили заполнению анкеты.\n\n"
        "На данном этапе мы не готовы пригласить вас в сообщество. "
        "Благодарим за понимание и желаем всего доброго."
    )
    await callback.message.answer(f"Кандидату {user_id} отправлено уведомление.")
    await callback.answer("Заявка отклонена.")


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬТЕ_НОВЫЙ_ТОКЕН_СЮДА":
        raise RuntimeError(
            "Не указан токен. Вставьте новый токен в BOT_TOKEN или задайте переменную окружения BOT_TOKEN."
        )
    init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен. Для остановки нажмите Ctrl+C.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
