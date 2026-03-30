import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8525815500:AAEbK5vc2H22YHnWAf0kvZ7g4PLNmlHcwQg"
ADMIN_ID   = 980725289

USERS = {
    "bigred_V1":   "Звіт про виконання робіт:",
    "bigred_G2":   "Звіт: Обсяг робіт/годин",
    "bigred_L3":   "Табель: Людино-години",
    "bigred_Z4": "Інше",
}

MONTHS_UA = {
    "01": "Січень",  "02": "Лютий",   "03": "Березень",
    "04": "Квітень", "05": "Травень",  "06": "Червень",
    "07": "Липень",  "08": "Серпень",  "09": "Вересень",
    "10": "Жовтень", "11": "Листопад", "12": "Грудень",
}

DB_FILE = "documents.json"

WAIT_PASSWORD = 0
WAIT_DOC_USER, WAIT_DOC_YEAR, WAIT_DOC_MONTH, WAIT_DOC_TYPE, WAIT_DOC_FILE = range(5)


def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Привіт! Введіть ваш пароль:")
    return WAIT_PASSWORD


async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    if password not in USERS:
        await update.message.reply_text("Невірний пароль. Спробуйте ще раз:")
        return WAIT_PASSWORD
    name = USERS[password]
    context.user_data["password"] = password
    context.user_data["name"] = name
    await show_years(update.message, context)
    return ConversationHandler.END


async def show_years(message_obj, context):
    password  = context.user_data["password"]
    name      = context.user_data["name"]
    db        = load_db()
    user_data = db.get(password, {})
    years = sorted(set(
        key.split("_")[0]
        for key in user_data.keys()
        if "_" in key
    ), reverse=True)
    if not years:
        await message_obj.reply_text(f"Привіт, {name}!\n\nДокументів ще немає.")
        return
    keyboard = [[InlineKeyboardButton(y, callback_data=f"year_{y}")] for y in years]
    await message_obj.reply_text(f"Привіт, {name}! Оберіть рік:", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    year = query.data.replace("year_", "")
    context.user_data["year"] = year
    password  = context.user_data["password"]
    db        = load_db()
    user_data = db.get(password, {})
    months = sorted(set(
        key.split("_")[1]
        for key in user_data.keys()
        if key.startswith(f"{year}_")
    ))
    if not months:
        await query.edit_message_text(f"У {year} році документів немає.")
        return
    keyboard = [[InlineKeyboardButton(MONTHS_UA[m], callback_data=f"month_{m}")] for m in months]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_years")])
    await query.edit_message_text(f"Рік: {year}\nОберіть місяць:", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month = query.data.replace("month_", "")
    context.user_data["month"] = month
    year      = context.user_data["year"]
    password  = context.user_data["password"]
    db        = load_db()
    user_data = db.get(password, {})
    month_name = MONTHS_UA[month]
    type_labels = {"daily": "Щоденні", "weekly": "Тижневі", "monthly": "Місячні"}
    types_available = [t for t in ["daily", "weekly", "monthly"] if user_data.get(f"{year}_{month}_{t}")]
    if not types_available:
        await query.edit_message_text(f"У {month_name} {year} документів немає.")
        return
    keyboard = [[InlineKeyboardButton(type_labels[t], callback_data=f"type_{t}")] for t in types_available]
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"year_{year}")])
    await query.edit_message_text(f"{month_name} {year} — оберіть тип:", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doc_type   = query.data.replace("type_", "")
    year       = context.user_data["year"]
    month      = context.user_data["month"]
    password   = context.user_data["password"]
    name       = context.user_data["name"]
    month_name = MONTHS_UA[month]
    db   = load_db()
    key  = f"{year}_{month}_{doc_type}"
    docs = db.get(password, {}).get(key, [])
    type_labels = {"daily": "Щоденні", "weekly": "Тижневі", "monthly": "Місячні"}
    keyboard = [[InlineKeyboardButton("Назад до типів", callback_data=f"month_{month}")]]
    if not docs:
        await query.edit_message_text(f"Документів немає.\n({type_labels[doc_type]}, {month_name} {year})", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    await query.edit_message_text(f"{name} — {type_labels[doc_type]}, {month_name} {year}\nНадсилаю {len(docs)} файл(ів)...", reply_markup=InlineKeyboardMarkup(keyboard))
    for doc in docs:
        await context.bot.send_document(chat_id=query.message.chat_id, document=doc["file_id"], caption=doc.get("filename", ""))


async def back_to_years(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_years(query.message, context)


async def admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Тільки для адміністратора.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(name, callback_data=f"auser_{pw}")] for pw, name in USERS.items()]
    await update.message.reply_text("Для кого завантажуємо?", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_DOC_USER


async def admin_select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    password = query.data.replace("auser_", "")
    context.user_data["target_password"] = password
    context.user_data["target_name"]     = USERS[password]
    from datetime import datetime
    cur_year = datetime.now().year
    years = [str(cur_year), str(cur_year - 1)]
    keyboard = [[InlineKeyboardButton(y, callback_data=f"ayear_{y}")] for y in years]
    await query.edit_message_text(f"Рік для {USERS[password]}?", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_DOC_YEAR


async def admin_select_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    year = query.data.replace("ayear_", "")
    context.user_data["upload_year"] = year
    keyboard = [[InlineKeyboardButton(MONTHS_UA[m], callback_data=f"amonth_{m}")] for m in sorted(MONTHS_UA.keys())]
    await query.edit_message_text(f"Місяць для {context.user_data['target_name']} ({year})?", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_DOC_MONTH


async def admin_select_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month = query.data.replace("amonth_", "")
    context.user_data["upload_month"] = month
    keyboard = [
        [InlineKeyboardButton("Щоденний",  callback_data="atype_daily")],
        [InlineKeyboardButton("Тижневий",  callback_data="atype_weekly")],
        [InlineKeyboardButton("Місячний",  callback_data="atype_monthly")],
    ]
    name       = context.user_data["target_name"]
    month_name = MONTHS_UA[month]
    year       = context.user_data["upload_year"]
    await query.edit_message_text(f"Тип для {name} ({month_name} {year})?", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_DOC_TYPE


async def admin_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("atype_", "")
    context.user_data["upload_type"] = doc_type
    name       = context.user_data["target_name"]
    month_name = MONTHS_UA[context.user_data["upload_month"]]
    year       = context.user_data["upload_year"]
    await query.edit_message_text(f"Надішліть файл для {name}\n{month_name} {year}")
    return WAIT_DOC_FILE


async def admin_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Надішліть файл.")
        return WAIT_DOC_FILE
    password   = context.user_data["target_password"]
    name       = context.user_data["target_name"]
    year       = context.user_data["upload_year"]
    month      = context.user_data["upload_month"]
    doc_type   = context.user_data["upload_type"]
    month_name = MONTHS_UA[month]
    key        = f"{year}_{month}_{doc_type}"
    db = load_db()
    if password not in db:
        db[password] = {}
    if key not in db[password]:
        db[password][key] = []
    db[password][key].append({"file_id": doc.file_id, "filename": doc.file_name})
    save_db(db)
    await update.message.reply_text(f"Збережено!\nДля: {name}\n{month_name} {year}\nФайл: {doc.file_name}\n\nДодати ще — /upload")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAIT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", admin_upload)],
        states={
            WAIT_DOC_USER:  [CallbackQueryHandler(admin_select_user,  pattern="^auser_")],
            WAIT_DOC_YEAR:  [CallbackQueryHandler(admin_select_year,  pattern="^ayear_")],
            WAIT_DOC_MONTH: [CallbackQueryHandler(admin_select_month, pattern="^amonth_")],
            WAIT_DOC_TYPE:  [CallbackQueryHandler(admin_select_type,  pattern="^atype_")],
            WAIT_DOC_FILE:  [MessageHandler(filters.Document.ALL, admin_receive_file)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(user_conv)
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(handle_year,   pattern="^year_"))
    app.add_handler(CallbackQueryHandler(handle_month,  pattern="^month_"))
    app.add_handler(CallbackQueryHandler(handle_type,   pattern="^type_"))
    app.add_handler(CallbackQueryHandler(back_to_years, pattern="^back_to_years$"))
    print("Бот запущено!")
    app.run_polling()

if __name__ == "__main__":
    main()
