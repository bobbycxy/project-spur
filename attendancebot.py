import logging
from datetime import datetime
from typing import Dict

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from dynamodbhelperv1 import DynamoDBHelper
db = DynamoDBHelper()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

LOGIN_REPLY, CHOOSING_CELL, CHOOSING_MONTH, CHOOSING_DAY, CHOOSING_MEMBERS, REMOVING_MEMBERS = range(6)

reply_keyboard = sorted([[item] for item in db.get_cell_groups()])
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


## helper function
def facts_to_str(user_data: Dict[str, str]) -> str:
    """Helper function for formatting the gathered user info."""
    facts = [f"{key}: {value}\n" for key, value in user_data.items() if key != 'Attendees'] + [f"{key} ({len(value)}):" for key, value in user_data.items() if key == 'Attendees']

    if 'Attendees' in user_data.keys():
        for n, item in enumerate(user_data['Attendees']):
            facts.append(f'{n+1}. {item}')

    return "\n".join(facts).join(["\n", "\n"])


## /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for verification."""
    await update.message.reply_text(
        "Hi! This is an attendance bot for PoD, the youth ministry of COSB."
        " In order to verify our users, kindly insert verification code."
    )

    return LOGIN_REPLY


## /select_cell
async def select_cell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user to select cell group"""
    await update.message.reply_text(
        "Welcome!"
        " What cell group are we taking attendance for?",
        reply_markup=markup,
    )

    return CHOOSING_CELL


## selecting the month
async def select_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user for the month selection."""
    text = update.message.text
    context.user_data["Cell"] = text

    ## prepare a keyboard for the number of months
    reply_keyboard = [['Jan','Feb','Mar'],['Apr','May','Jun'],['Jul','Aug','Sep'],['Oct','Nov','Dec']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        f"You have selected {text}!"
        " What month are we taking attendance for?",
        reply_markup=markup,
    )

    return CHOOSING_MONTH


## selecting the day
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user for the day selection."""
    text = update.message.text
    context.user_data["month"] = text
    print(context.user_data["Cell"],db.get_cell_members(context.user_data["Cell"]))

    ## prepare a keyboard for the number of months
    reply_keyboard = [['1','2','3'],['4','5','6'],['7','8','9'],['10','11','12'],['13','14','15'],['16','17','18'],['19','20','21'],['22','23','24'],['25','26','27'],['28','29','30'],['31']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        f"You have selected {context.user_data['Cell']}, and are taking attendance for the month of {text}!"
        " What day are we taking attendance for?",
        reply_markup=markup,
    )

    return CHOOSING_DAY


async def regular_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for info about the selected predefined choice."""
    text = update.message.text
    context.user_data["day"] = text
    cell_members = db.get_cell_members(context.user_data["Cell"])
    attendance_date = str(datetime.now().year) + f'-{context.user_data["month"]}-{context.user_data["day"]}'
    context.user_data["Date"] = attendance_date

    del context.user_data["month"]
    del context.user_data["day"]

    reply_keyboard = sorted([[name] for name in cell_members]) + [['REMOVE','DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        f"You have selected {context.user_data['Cell']}, for the date of {attendance_date}."
        " Who are the members who attended?",
        reply_markup=markup,
    )

    return CHOOSING_MEMBERS


async def received_information(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for the next category."""

    user_data = context.user_data
    print(user_data)
    text = update.message.text
    if text != 'DONE':
        if 'Attendees' not in user_data.keys():
            user_data['Attendees'] = []
        if text not in user_data['Attendees']:
            user_data['Attendees'].append(text)

    # del user_data["choice"]

    cell_members = db.get_cell_members(user_data["Cell"])

    reply_keyboard = sorted([[name] for name in cell_members]) + [['REMOVE','DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Neat! Just so you know, this is what you already told me:\n"
        f"{facts_to_str(user_data)}\nAny more members?",
        reply_markup=markup,
    )

    return CHOOSING_MEMBERS


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for the next category."""

    user_data = context.user_data

    # del user_data["choice"]

    attendees = user_data['Attendees']

    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Got it, you want to remove some names.\n"
        f"{facts_to_str(user_data)}\nWho would you like to remove?",
        reply_markup=markup,
    )

    return REMOVING_MEMBERS

async def remove_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for the next category."""

    user_data = context.user_data
    text = update.message.text
    user_data['Attendees'].remove(text)
    # del user_data["choice"]

    attendees = user_data['Attendees']

    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Okay, I've removed the member.\n"
        f"{facts_to_str(user_data)}\nWho else would you like to remove?\nIf you have finished removing, press 'DONE'",
        reply_markup=markup,
    )

    return REMOVING_MEMBERS


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data
    # if "choice" in user_data:
    #     del user_data["choice"]

    await update.message.reply_text(
        f"I collected these information:\n {facts_to_str(user_data)}\nI will proceed to update their attendance now.",
        reply_markup=ReplyKeyboardRemove(),
    )

    attendance_date = datetime.strptime(user_data['Date'], '%Y-%b-%d')

    for attendee in user_data['Attendees']:
        db.add_attendance(user_data['Cell'], attendance_date, attendee)

    user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("6442474812:AAErk9hYBRplDsW94bxQ8b0r3Zx2EW8Vjfg").build()

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOGIN_REPLY: [
                MessageHandler(
                    filters.Regex("^(podYouths#159)$"), select_cell
                )            ],
            CHOOSING_CELL: [
                MessageHandler(
                    filters.Regex("^(ONE|Bouquet|Kadesh|Gilead)$"), select_month
                )            ],
            CHOOSING_MONTH: [
                MessageHandler(
                    filters.Regex("^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$"), select_day
                )            ],
            CHOOSING_DAY: [
                MessageHandler(
                    filters.Regex("^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31)$"), regular_choice
                )            ],
            CHOOSING_MEMBERS: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$") | filters.Regex("^REMOVE$")), received_information
                ),
                MessageHandler(filters.Regex("^REMOVE$"), remove),
            ],
            REMOVING_MEMBERS: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$")), remove_update
                ),
                MessageHandler(filters.Regex("^DONE$"), received_information),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^DONE$"), done)],
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
