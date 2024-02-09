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

from dynamodbhelperv4 import DynamoDBHelper
db = DynamoDBHelper()

################################### Enable logging ################################### 
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

LOGIN_REPLY, CHOOSING_CELL, CHOOSING_MONTH, CHOOSING_DAY, CHOOSING_MEMBERS_PRESENT, REMOVING_MEMBERS_PRESENT, CHOOSING_MEMBERS_VALABS, REMOVING_MEMBERS_VALABS = range(8)

reply_keyboard = sorted([[item] for item in db.get_cell_groups()])
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


################################### Helper Function ################################### 
def facts_to_str(user_data: Dict[str, str]) -> str:
    """Helper function for formatting the gathered user info."""
    facts = [f"{key}: {value}\n" for key, value in user_data.items() if key not in ['Attendees','Valid Absentees']] 

    if 'Attendees' in user_data.keys():
        facts = facts + [f"{key} ({len(value)}):" for key, value in user_data.items() if key == 'Attendees']
        for n, item in enumerate(user_data['Attendees']):
            facts.append(f'{n+1}. {item}')

    if 'Valid Absentees' in user_data.keys():
        facts = facts + [f"\n{key} ({len(value)}):" for key, value in user_data.items() if key == 'Valid Absentees']
        for n, item in enumerate(user_data['Valid Absentees']):
            facts.append(f'{n+1}. {item}')
        
    print(facts)
    return "\n".join(facts).join(["\n", "\n"])

def get_relevant_cell_members(cell_group, date, selected_members = []):
    have_existing_attendance = False
    attended_cell_members, absentvalid_cell_members = [], []

    cell_members = db.get_cell_members(cell_group)
    clean_date = datetime.strptime(date, '%Y-%b-%d')
    entered_cell_members = db.get_alr_entered_cell_members(cell_group, clean_date)
    attended_cell_members = db.get_alr_attended_cell_members(cell_group, clean_date)
    absentvalid_cell_members = db.get_alr_absentvalid_cell_members(cell_group, clean_date)
    relevant_cell_members = list(set(cell_members) - set(entered_cell_members) - set(selected_members)) 
    if len(entered_cell_members) > 0:
        have_existing_attendance = True
    return relevant_cell_members, have_existing_attendance, attended_cell_members, absentvalid_cell_members


################################### State Function ################################### 
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


## selecting cell members
async def regular_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for cell members who attended."""
    text = update.message.text
    context.user_data["day"] = text

    attendance_date = str(datetime.now().year) + f'-{context.user_data["month"]}-{context.user_data["day"]}'
    context.user_data["Date"] = attendance_date
    del context.user_data["month"]
    del context.user_data["day"]

    relevant_cell_members, have_existing_attendance, attended_cell_members, absentvalid_cell_members = get_relevant_cell_members(context.user_data["Cell"], context.user_data['Date'])

    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','NONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    if have_existing_attendance:
        context.user_data['Attendees'] = sorted(attended_cell_members)
        context.user_data['Valid Absentees'] = sorted(absentvalid_cell_members)

        await update.message.reply_text(
            "Neat! Just so you know, this is what you already told me:\n"
            f"{facts_to_str(context.user_data)}\nAny more members?",
            reply_markup=markup,
        )
    else:
        await update.message.reply_text(
            f"You have selected {context.user_data['Cell']}, for the date of {attendance_date}."
            " Who are the members who attended?",
            reply_markup=markup,
        )

    return CHOOSING_MEMBERS_PRESENT


## Storing the information and asking for more cell members
async def received_information(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members who attended"""

    user_data = context.user_data
    print(user_data)
    text = update.message.text
    if text != 'DONE':
        if 'Attendees' not in user_data.keys():
            user_data['Attendees'] = []
        if text not in user_data['Attendees']:
            user_data['Attendees'].append(text)

    # del user_data["choice"]

    # cell_members = db.get_cell_members(user_data["Cell"])
    relevant_cell_members, _, _, _ = get_relevant_cell_members(context.user_data["Cell"], context.user_data['Date'], context.user_data["Attendees"])

    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Neat! Just so you know, this is what you already told me:\n"
        f"{facts_to_str(user_data)}\nAny more members?",
        reply_markup=markup,
    )

    return CHOOSING_MEMBERS_PRESENT


## removing cell members
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adk the user for the cell members they want to remove from their current selected list"""

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

    return REMOVING_MEMBERS_PRESENT


## Storing the information and asking for more cell members to remove
async def remove_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members they want to remove"""

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

    return REMOVING_MEMBERS_PRESENT


## done
async def regular_choice1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data

    relevant_cell_members, _, _, _ = get_relevant_cell_members(context.user_data["Cell"], context.user_data['Date'], context.user_data.get('Attendees',[]))
    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','NONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        f"Thank you. I have collected these information:\n {facts_to_str(user_data)}\nNext, what about members who are absent with valid reason? If no one is absent with valid reason, simply select the option 'NONE'.",
        reply_markup=markup,
    )

    return CHOOSING_MEMBERS_VALABS


## Storing the information and asking for more cell members
async def received_information1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members who attended"""

    user_data = context.user_data
    print(user_data)
    text = update.message.text
    if text != 'DONE':
        if 'Valid Absentees' not in user_data.keys():
            user_data['Valid Absentees'] = []
        if text not in user_data['Valid Absentees']:
            user_data['Valid Absentees'].append(text)

    # del user_data["choice"]

    # cell_members = db.get_cell_members(user_data["Cell"])
    relevant_cell_members, _, _, _ = get_relevant_cell_members(context.user_data["Cell"], context.user_data['Date'], context.user_data.get('Attendees',[]) + context.user_data['Valid Absentees'])

    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Neat! Just so you know, this is what you already told me:\n"
        f"{facts_to_str(user_data)}\nAny more members?",
        reply_markup=markup,
    )

    return CHOOSING_MEMBERS_VALABS


## removing cell members
async def remove1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for the cell members they want to remove from their current selected list"""

    user_data = context.user_data

    # del user_data["choice"]

    attendees = user_data['Valid Absentees']

    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Got it, you want to remove some names.\n"
        f"{facts_to_str(user_data)}\nWho would you like to remove?",
        reply_markup=markup,
    )

    return REMOVING_MEMBERS_VALABS

## Storing the information and asking for more cell members to remove
async def remove_update1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members they want to remove"""

    user_data = context.user_data
    text = update.message.text
    user_data['Valid Absentees'].remove(text)
    # del user_data["choice"]

    attendees = user_data['Valid Absentees']

    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Okay, I've removed the member.\n"
        f"{facts_to_str(user_data)}\nWho else would you like to remove?\nIf you have finished removing, press 'DONE'",
        reply_markup=markup,
    )

    return REMOVING_MEMBERS_VALABS

## done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data
    # if "choice" in user_data:
    #     del user_data["choice"]

    attendance_date = datetime.strptime(user_data['Date'], '%Y-%b-%d')

    if 'Attendees' in user_data.keys():
        not_yet_added_cell_members = list(set(user_data['Attendees']) - set(db.get_alr_entered_cell_members(user_data['Cell'], attendance_date)))
        for attendee in not_yet_added_cell_members:
            db.add_attendance(user_data['Cell'], attendance_date, attendee, "Present")
        
        existing_cell_members = list(set(user_data['Attendees']).intersection(db.get_cell_members(user_data['Cell'])))
        new_cell_members = list(set(user_data['Attendees']) - set(existing_cell_members))
        for attendee in new_cell_members:
            db.add_new_member(attendee, 'New Friend', user_data['Cell'], 'None', '01-01-2000')


    if 'Valid Absentees' in user_data.keys():
        not_yet_added_cell_members = list(set(user_data['Valid Absentees']) - set(db.get_alr_entered_cell_members(user_data['Cell'], attendance_date)))
        for attendee in not_yet_added_cell_members:
            db.add_attendance(user_data['Cell'], attendance_date, attendee, "Absent Valid")

    await update.message.reply_text(
        f"Thank you {update.effective_user.first_name}. As a recap, I have collected these information:\n {facts_to_str(user_data)}\nI have proceeded to update their attendance now. Type '/start' to begin a new attendance.",
        reply_markup=ReplyKeyboardRemove(),
    )

    user_data.clear()
    return ConversationHandler.END


## restart
async def exit_(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data

    await update.message.reply_text(
        "Type '/start' to begin a new attendance.",
        )

    user_data.clear()
    return ConversationHandler.END


############################### MAIN() ###############################
def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("6974224424:AAFWj2U248mXcVWD4SJ5p8UPEMtChbIYS8s").build()

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOGIN_REPLY: [
                MessageHandler(
                    filters.Regex("^(podYouths#159)$"), select_cell
                ),
                # CommandHandler("exit", exit_),
                            ],
            CHOOSING_CELL: [
                MessageHandler(
                    filters.Regex("^(ONE|Bouquet|Kadesh|Gilead)$"), select_month
                ),
                # CommandHandler("exit", exit_),
                            ],
            CHOOSING_MONTH: [
                MessageHandler(
                    filters.Regex("^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$"), select_day
                ),
                # CommandHandler("exit", exit_),
                            ],
            CHOOSING_DAY: [
                MessageHandler(
                    filters.Regex("^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31)$"), regular_choice
                ),
                # CommandHandler("exit", exit_),
                            ],
            CHOOSING_MEMBERS_PRESENT: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$") | filters.Regex("^REMOVE$") | filters.Regex("^NONE$")), received_information
                ),
                MessageHandler(filters.Regex("^REMOVE$"), remove),
                MessageHandler(filters.Regex("^(DONE|NONE)$"), regular_choice1),
                # CommandHandler("exit", exit_),
            ],
            REMOVING_MEMBERS_PRESENT: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$")), remove_update
                ),
                MessageHandler(filters.Regex("^DONE$"), received_information),
                # CommandHandler("exit", exit_),
            ],
            CHOOSING_MEMBERS_VALABS: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$") | filters.Regex("^REMOVE$") | filters.Regex("^NONE$")), received_information1
                ),
                MessageHandler(filters.Regex("^REMOVE$"), remove1),
                MessageHandler(filters.Regex("^(DONE|NONE)$"), done),
                # CommandHandler("exit", exit_),
            ],
            REMOVING_MEMBERS_VALABS: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$")), remove_update1
                ),
                MessageHandler(filters.Regex("^DONE$"), received_information1),
                # CommandHandler("exit", exit_),
            ],
        },
        fallbacks=[CommandHandler("exit", exit_)],
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
