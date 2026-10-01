"""
Telegram check-in bot that logs daily check-ins / check-outs to a Google Sheet.

Setup: see README.md. Copy config.example.py to config.py and fill it in.
"""

from datetime import datetime

import gspread
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

try:
    import config
except ImportError:
    raise SystemExit(
        "config.py not found. Copy config.example.py to config.py and fill in"
        " your values (see README.md)."
    )

# Optional: only needed if you run the bot inside Jupyter / Google Colab.
try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Google Sheets connection
# ---------------------------------------------------------------------------
gc = gspread.service_account(filename=config.GOOGLE_CREDENTIALS_FILE)
sh = gc.open_by_url(config.GOOGLE_SHEET_URL)
worksheet = sh.sheet1

TZ = pytz.timezone(config.TIMEZONE)

# Sheet column numbers (1-based). Row 1 of your sheet must contain headers.
COL_CHECKIN_TIME = 1   # A - date & time of check-in
COL_NAME = 2           # B - full name
COL_EMAIL = 3          # C - email
COL_PLAN_PROGRAM = 4   # D - planned topic for the day
COL_PLAN_WEEK = 5      # E - planned week
COL_LATE_REASON = 6    # F - reason for being late (filled in manually)
COL_CHECKOUT_TIME = 7  # G - date & time of check-out
COL_ASSIGNED_BY = 8    # H - who assigned the task
COL_LEARNING = 9       # I - learning done ("<topic> - Week N")
COL_DAYOFF = 10        # J - day off / holiday marker
COL_TASK_TEXT = 11     # K - description of the task done
TOTAL_COLUMNS = 11

# Conversation states for registration
GET_NAME, GET_SURNAME, GET_EMAIL = range(3)

# NOTE: kept in memory only - users must register again after a restart.
USERS_DB = {}


# ---------------------------------------------------------------------------
# Keyboard helpers
# ---------------------------------------------------------------------------
def back_button(callback_data):
  return [InlineKeyboardButton("Back", callback_data=callback_data)]


def get_main_menu_keyboard():
  keyboard = [
      [InlineKeyboardButton("Check-in", callback_data="menu_checkin")],
      [InlineKeyboardButton("Check-out", callback_data="menu_checkout")],
      [InlineKeyboardButton("Day off / Holiday", callback_data="menu_dayoff")],
  ]
  return InlineKeyboardMarkup(keyboard)


def program_keyboard(prefix, back_to, allow_other=False):
  """One button per entry in config.PROGRAMS (+ optional 'Other')."""
  keyboard = [
      [InlineKeyboardButton(p, callback_data=f"{prefix}_prog_{p}")]
      for p in config.PROGRAMS
  ]
  if allow_other:
    keyboard.append(
        [InlineKeyboardButton("Other", callback_data=f"{prefix}_other_prog")]
    )
  keyboard.append(back_button(back_to))
  return InlineKeyboardMarkup(keyboard)


def week_keyboard(prefix, back_to):
  keyboard = [
      [InlineKeyboardButton(f"Week {i}", callback_data=f"{prefix}_week_{i}")]
      for i in range(config.NUMBER_OF_WEEKS)
  ]
  keyboard.append(back_button(back_to))
  return InlineKeyboardMarkup(keyboard)


def mentor_keyboard(prefix, back_to):
  keyboard = [
      [InlineKeyboardButton(m, callback_data=f"{prefix}_mentor_{m}")]
      for m in config.MENTORS
  ]
  keyboard.append(back_button(back_to))
  return InlineKeyboardMarkup(keyboard)


def get_exit_type_keyboard():
  keyboard = [
      [InlineKeyboardButton("1) Learning only", callback_data="c_learning")],
      [InlineKeyboardButton("2) Task only", callback_data="c_task")],
      [InlineKeyboardButton("3) Both", callback_data="c_both")],
      back_button("back_to_main_menu"),
  ]
  return InlineKeyboardMarkup(keyboard)


def value_of(data):
  """Return everything after the second underscore (keeps names intact)."""
  return data.split("_", 2)[2]


# ---------------------------------------------------------------------------
# Sheet helpers
# ---------------------------------------------------------------------------
def check_and_add_date_header(current_date_str):
  """When a new day starts, add two blank rows and a copy of the header row."""
  all_values = worksheet.get_all_values()

  if len(all_values) <= 1:
    return

  date_header_exists = any(
      row and any(current_date_str in str(cell) for cell in row)
      for row in all_values
  )

  if not date_header_exists:
    worksheet.append_row([])
    worksheet.append_row([])

    headers = all_values[0]
    worksheet.append_row(headers)
    last_row = len(worksheet.get_all_values())

    worksheet.format(
        f"A{last_row}:K{last_row}",
        {
            "textFormat": {
                "bold": True,
                "fontSize": 10,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "backgroundColor": {"red": 0.22, "green": 0.58, "blue": 0.29},
        },
    )


def last_row_number():
  return len(worksheet.get_all_values())


# ---------------------------------------------------------------------------
# Registration flow
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id in USERS_DB:
    await update.message.reply_text(
        "You are already registered! Type /menu to open the main menu."
    )
    return ConversationHandler.END

  await update.message.reply_text("Welcome! Please enter your first name:")
  return GET_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
  context.user_data["name"] = update.message.text
  await update.message.reply_text("Now enter your last name:")
  return GET_SURNAME


async def get_surname(update: Update, context: ContextTypes.DEFAULT_TYPE):
  context.user_data["surname"] = update.message.text
  await update.message.reply_text("Please enter your email address:")
  return GET_EMAIL


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  email = update.message.text
  full_name = f"{context.user_data['name']} {context.user_data['surname']}"
  USERS_DB[user_id] = {"full_name": full_name, "email": email}

  await update.message.reply_text(
      "Registration complete! Type /menu to open the main menu."
  )
  return ConversationHandler.END


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "Please choose an option:", reply_markup=get_main_menu_keyboard()
  )


# ---------------------------------------------------------------------------
# Button handler
# ---------------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data
  user_id = query.from_user.id
  now = datetime.now(TZ)
  current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
  current_date_str = now.strftime("%Y-%m-%d")

  user_info = USERS_DB.get(user_id, {"full_name": "Unknown", "email": ""})
  full_name = user_info["full_name"]

  # --- "Back" buttons ---
  if data == "back_to_main_menu":
    await query.edit_message_text(
        "Please choose an option:", reply_markup=get_main_menu_keyboard()
    )
    return
  elif data == "back_to_checkin_prog":
    await query.edit_message_text(
        "Daily plan - choose what you will work on:",
        reply_markup=program_keyboard("checkin", "back_to_main_menu"),
    )
    return
  elif data == "back_to_exit_type":
    await query.edit_message_text(
        "Choose the check-out type:", reply_markup=get_exit_type_keyboard()
    )
    return
  elif data == "back_to_clearn_prog":
    await query.edit_message_text(
        "Choose the learning topic:",
        reply_markup=program_keyboard("clearn", "back_to_exit_type", True),
    )
    return
  elif data == "back_to_cboth_prog":
    await query.edit_message_text(
        "Choose the learning topic:",
        reply_markup=program_keyboard("cboth", "back_to_exit_type", True),
    )
    return
  elif data == "back_to_cboth_week":
    prog_name = context.user_data.get("cb_prog", "")
    await query.edit_message_text(
        f"Selected: {prog_name}. Choose the week:",
        reply_markup=week_keyboard("cboth", "back_to_cboth_prog"),
    )
    return

  check_and_add_date_header(current_date_str)

  # --- 1. CHECK-IN ---
  if data == "menu_checkin":
    all_values = worksheet.get_all_values()
    already_checked_in = any(
        row
        and len(row) > 1
        and current_date_str in str(row[0])
        and row[1] == full_name
        and row[0] != current_date_str
        for row in all_values
    )

    if already_checked_in:
      await query.edit_message_text(
          "⚠️ You have already checked in today.\n\nType /menu for the main"
          " menu."
      )
      return

    row = [current_time_str, full_name, user_info["email"]]
    row += [""] * (TOTAL_COLUMNS - len(row))
    worksheet.append_row(row)
    context.user_data["last_row"] = last_row_number()

    await query.edit_message_text(
        "Daily plan - choose what you will work on:",
        reply_markup=program_keyboard("checkin", "back_to_main_menu"),
    )

  elif data.startswith("checkin_prog_"):
    prog_name = value_of(data)
    context.user_data["selected_prog"] = prog_name
    await query.edit_message_text(
        f"Selected: {prog_name}. Choose the week:",
        reply_markup=week_keyboard("checkin", "back_to_checkin_prog"),
    )

  elif data.startswith("checkin_week_"):
    week_num = value_of(data)
    prog_name = context.user_data.get("selected_prog", "")
    row_no = context.user_data.get("last_row")
    if row_no:
      worksheet.update_cell(row_no, COL_PLAN_PROGRAM, prog_name)
      worksheet.update_cell(row_no, COL_PLAN_WEEK, week_num)
    await query.edit_message_text(
        f"Welcome! Your plan was saved: {prog_name}, Week {week_num}"
    )

  # --- 2. DAY OFF / HOLIDAY ---
  elif data == "menu_dayoff":
    all_values = worksheet.get_all_values()
    target_row = None

    for idx, row in enumerate(all_values, start=1):
      if (
          row
          and len(row) > 1
          and current_date_str in str(row[0])
          and row[1] == full_name
      ):
        target_row = idx
        break

    if target_row:
      worksheet.update_cell(target_row, COL_DAYOFF, "Day off / Holiday")
    else:
      row = [current_time_str, full_name, user_info["email"]]
      row += [""] * (COL_DAYOFF - 1 - len(row))
      row.append("Day off / Holiday")
      worksheet.append_row(row)

    await query.edit_message_text("Enjoy your time off! 🌴")

  # --- 3. CHECK-OUT ---
  elif data == "menu_checkout":
    await query.edit_message_text(
        "Choose the check-out type:", reply_markup=get_exit_type_keyboard()
    )

  # A) Learning only
  elif data == "c_learning":
    await query.edit_message_text(
        "Choose the learning topic:",
        reply_markup=program_keyboard("clearn", "back_to_exit_type", True),
    )

  elif data.startswith("clearn_prog_"):
    prog_name = value_of(data)
    context.user_data["c_prog"] = prog_name
    await query.edit_message_text(
        f"Selected: {prog_name}. Choose the week:",
        reply_markup=week_keyboard("clearn", "back_to_clearn_prog"),
    )

  elif data == "clearn_other_prog":
    await query.edit_message_text(
        "Please type the name of the other topic as a message:"
    )
    context.user_data["awaiting_clearn_other"] = True

  elif data.startswith("clearn_week_"):
    week_num = value_of(data)
    prog = context.user_data.get("c_prog")
    learning_info = f"{prog} - Week {week_num}"

    row_no = last_row_number()
    worksheet.update_cell(row_no, COL_CHECKOUT_TIME, current_time_str)
    worksheet.update_cell(row_no, COL_LEARNING, learning_info)

    await query.edit_message_text("Thank you! Your data was saved. 🙏")

  # B) Task only
  elif data == "c_task":
    await query.edit_message_text(
        "Who assigned the task?",
        reply_markup=mentor_keyboard("ctask", "back_to_exit_type"),
    )

  elif data.startswith("ctask_mentor_"):
    mentor_name = value_of(data)
    context.user_data["mentor_name"] = mentor_name
    row_no = last_row_number()
    worksheet.update_cell(row_no, COL_CHECKOUT_TIME, current_time_str)
    worksheet.update_cell(row_no, COL_ASSIGNED_BY, mentor_name)

    await query.edit_message_text(
        "Please type a short description of the task you did as a message:"
    )
    context.user_data["awaiting_task_text"] = True

  # C) Both
  elif data == "c_both":
    await query.edit_message_text(
        "Choose the learning topic:",
        reply_markup=program_keyboard("cboth", "back_to_exit_type", True),
    )

  elif data.startswith("cboth_prog_"):
    prog_name = value_of(data)
    context.user_data["cb_prog"] = prog_name
    await query.edit_message_text(
        f"Selected: {prog_name}. Choose the week:",
        reply_markup=week_keyboard("cboth", "back_to_cboth_prog"),
    )

  elif data == "cboth_other_prog":
    await query.edit_message_text(
        "Please type the name of the other topic as a message:"
    )
    context.user_data["awaiting_cboth_other"] = True

  elif data.startswith("cboth_week_"):
    context.user_data["cb_week"] = value_of(data)
    await query.edit_message_text(
        "Who assigned the task?",
        reply_markup=mentor_keyboard("cboth", "back_to_cboth_week"),
    )

  elif data.startswith("cboth_mentor_"):
    mentor_name = value_of(data)
    prog = context.user_data.get("cb_prog")
    week = context.user_data.get("cb_week")
    learning_info = f"{prog} - Week {week}"

    row_no = last_row_number()
    worksheet.update_cell(row_no, COL_CHECKOUT_TIME, current_time_str)
    worksheet.update_cell(row_no, COL_ASSIGNED_BY, mentor_name)
    worksheet.update_cell(row_no, COL_LEARNING, learning_info)

    await query.edit_message_text(
        "Please type a short description of the task you did as a message:"
    )
    context.user_data["awaiting_task_text"] = True


# ---------------------------------------------------------------------------
# Free-text answers ("Other" topic, task description)
# ---------------------------------------------------------------------------
async def handle_text_messages(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  now = datetime.now(TZ)
  current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")

  if context.user_data.get("awaiting_clearn_other"):
    prog_text = update.message.text
    row_no = last_row_number()
    worksheet.update_cell(row_no, COL_CHECKOUT_TIME, current_time_str)
    worksheet.update_cell(row_no, COL_LEARNING, prog_text)
    context.user_data["awaiting_clearn_other"] = False
    await update.message.reply_text(
        "Thank you! Your learning topic was saved. 🙏"
    )

  elif context.user_data.get("awaiting_cboth_other"):
    context.user_data["cb_prog"] = update.message.text
    context.user_data["awaiting_cboth_other"] = False
    await update.message.reply_text(
        "Who assigned the task?",
        reply_markup=mentor_keyboard("cboth", "back_to_cboth_week"),
    )

  elif context.user_data.get("awaiting_task_text"):
    task_content = update.message.text
    row_no = last_row_number()
    worksheet.update_cell(row_no, COL_TASK_TEXT, task_content)
    context.user_data["awaiting_task_text"] = False
    await update.message.reply_text(
        "Thank you! Your task description and check-out data were saved. 🙏"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
  app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

  conv_handler = ConversationHandler(
      entry_points=[CommandHandler("start", start)],
      states={
          GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
          GET_SURNAME: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, get_surname)
          ],
          GET_EMAIL: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)
          ],
      },
      fallbacks=[],
  )

  app.add_handler(conv_handler)
  app.add_handler(CommandHandler("menu", menu))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages)
  )

  print("Bot is running... (press Ctrl+C to stop)")
  app.run_polling()


if __name__ == "__main__":
  main()
