import asyncio
import json
import os
import traceback

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

LOGIN_REPLY, CHOOSING_CELL, CHOOSING_MONTH, CHOOSING_DAY, CHOOSING_MEMBERS_ATTENDEES, REMOVING_MEMBERS_ATTENDEES, CHOOSING_MEMBERS_VALABSENTEES, REMOVING_MEMBERS_VALABSENTEES = range(8)

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

def get_relevant_cell_members(cell_group, date):
    """Helper function for gathering three sets of information:
      1. all cell members in the cell group, 
      2. attendees on the given date
      3. valid absentees on the given date"""
    attended_cell_members, absentvalid_cell_members = [], []
    clean_date = datetime.strptime(date, '%Y-%b-%d')
    
    all_cell_members = db.get_cell_members(cell_group)
    attended_cell_members = db.get_alr_attended_cell_members(cell_group, clean_date)
    absentvalid_cell_members = db.get_alr_absentvalid_cell_members(cell_group, clean_date)

    return all_cell_members, attended_cell_members, absentvalid_cell_members


################################### State Function ################################### 
## /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for verification."""
    await update.message.reply_text(
        f"Hi! This is an attendance bot for PoD, the youth ministry of COSB. If you wish to exit the attendance taking at any point of this exercise, simple type '/exit'."
        "\n\n<b>Before we begin, I have to verify you. Please kindly insert the verification code.</b>",
        parse_mode = 'HTML'
    )

    return LOGIN_REPLY


## /select_cell
async def select_cell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user to select cell group"""
    await update.message.reply_text(
        f"Welcome {update.effective_user.first_name}!"
        " What cell group are we taking attendance for?",
        reply_markup=markup,
        parse_mode = 'HTML'
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
        parse_mode = 'HTML'
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
        parse_mode = 'HTML'
    )

    return CHOOSING_DAY


## selecting cell members
async def regular_choice_attendees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for cell members who attended."""
    text = update.message.text
    context.user_data["day"] = text

    ## store into the context object the user's date
    attendance_date = str(datetime.now().year) + f'-{context.user_data["month"]}-{context.user_data["day"]}'
    context.user_data["Date"] = attendance_date
    del context.user_data["month"]
    del context.user_data["day"]

    ## prepare lists of the relevant cell members
    all_cell_members, attended_cell_members, absentvalid_cell_members = get_relevant_cell_members(context.user_data["Cell"], context.user_data['Date'])
    context.user_data['Attendees'] = sorted(attended_cell_members)
    context.user_data['Valid Absentees'] = sorted(absentvalid_cell_members)
    relevant_cell_members = list(set(all_cell_members) - set(context.user_data['Attendees']) - set(context.user_data['Valid Absentees']))

    ## prepare the keyboard object
    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','NONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Neat! Let's begin with our attendees. Who was present?</b>\n"
        f"{facts_to_str(context.user_data)}\n<i>Instructions: Select 'REMOVE' to remove attendees. Select 'NONE' if no attendees to add."
        " If there are new friends, type in their name! Preferably their first and last name, e.g. Nehemiah Tan.</i>",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return CHOOSING_MEMBERS_ATTENDEES


## Storing the information and asking for more cell members
async def received_information_attendees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members who attended"""

    user_data = context.user_data
    print(user_data)
    text = update.message.text
    if text != 'DONE':
        if text not in user_data['Attendees']:
            user_data['Attendees'].append(text)

    ## prepare lists of the relevant cell members
    all_cell_members = db.get_cell_members(user_data["Cell"])
    relevant_cell_members = list(set(all_cell_members) - set(context.user_data['Attendees']) - set(context.user_data['Valid Absentees']))

    ## prepare the keyboard object
    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Got it! Any more attendees?</b>\n"
        f"{facts_to_str(user_data)}\n<i>Instructions: Select 'REMOVE' to remove attendees. Select 'DONE' if no more attendees to add.</i>",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return CHOOSING_MEMBERS_ATTENDEES


## removing cell members
async def remove_attendees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for the cell members they want to remove from the attendees list"""

    user_data = context.user_data

    ## prepare lists of the relevant cell members
    attendees = user_data['Attendees']

    ## prepare the keyboard object
    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Okay, you want to remove names from the list of attendees. Who would you like to remove?</b>\n"
        f"{facts_to_str(user_data)}",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return REMOVING_MEMBERS_ATTENDEES


## Storing the information and asking for more cell members to remove
async def remove_attendees_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members they want to remove from the attendees list"""

    user_data = context.user_data
    text = update.message.text
    user_data['Attendees'].remove(text)
    
    ## if the member to be removed is already in the database, then we must delete it.
    if text in db.get_alr_attended_cell_members(user_data['Cell'], datetime.strptime(user_data['Date'], '%Y-%b-%d')):
        db.del_alr_attended_cell_members(text, user_data['Cell'], datetime.strptime(user_data['Date'], '%Y-%b-%d'))

    ## prepare lists of the relevant cell members
    attendees = user_data['Attendees']

    ## prepare the keyboard object
    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Okay, I've removed the member. Who else would you like to remove?</b>\n"
        f"{facts_to_str(user_data)}\n<i>Instructions: If you have finished removing, press 'DONE'.</i>",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return REMOVING_MEMBERS_ATTENDEES


## selecting cell members
async def regular_choice_valabsentees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for cell members who were valid absentees"""
    user_data = context.user_data

    ## prepare lists of the relevant cell members
    all_cell_members = db.get_cell_members(user_data["Cell"])
    relevant_cell_members = list(set(all_cell_members) - set(context.user_data['Attendees']) - set(context.user_data['Valid Absentees']))

    ## prepare the keyboard object
    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','NONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        f"<b>Great, let's move to our valid absentees. Who was absent with valid reasons?</b>\n {facts_to_str(user_data)}\n<i>Instructions: Select 'REMOVE' to remove valid absentees. Select 'NONE' if no valid absentees to add.</i>",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return CHOOSING_MEMBERS_VALABSENTEES


## Storing the information and asking for more cell members
async def received_information_valabsentees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members who were valid absentees"""

    user_data = context.user_data
    print(user_data)
    text = update.message.text
    if text != 'DONE':
        if 'Valid Absentees' not in user_data.keys():
            user_data['Valid Absentees'] = []
        if text not in user_data['Valid Absentees']:
            user_data['Valid Absentees'].append(text)

    ## prepare lists of the relevant cell members
    all_cell_members = db.get_cell_members(user_data["Cell"])
    relevant_cell_members = list(set(all_cell_members) - set(context.user_data['Attendees']) - set(context.user_data['Valid Absentees']))

    ## prepare the keyboard object
    reply_keyboard = sorted([[name] for name in relevant_cell_members]) + [['REMOVE','DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Got it! Any more valid absentees?</b>\n"
        f"{facts_to_str(user_data)}\n<i>Instructions: Select 'REMOVE' to remove valid absentees. Select 'DONE' if no more valid absentees to add.</i>",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return CHOOSING_MEMBERS_VALABSENTEES


## removing cell members
async def remove_valabsentees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for the cell members they want to remove from their current selected list"""

    user_data = context.user_data

    ## prepare lists of the relevant cell members
    attendees = user_data['Valid Absentees']

    ## prepare the keyboard object
    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Okay, you want to remove names from the list of valid absentees. Who would you like to remove?</b>\n"
        f"{facts_to_str(user_data)}",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return REMOVING_MEMBERS_VALABSENTEES


## Storing the information and asking for more cell members to remove
async def remove_valabsentees_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for any more members they want to remove"""

    user_data = context.user_data
    text = update.message.text
    user_data['Valid Absentees'].remove(text)
    
    ## if the member to be removed is already in the database, then we must delete it.
    if text in db.get_alr_absentvalid_cell_members(user_data['Cell'], datetime.strptime(user_data['Date'], '%Y-%b-%d')):
        db.del_alr_absentvalid_cell_members(text, user_data['Cell'], datetime.strptime(user_data['Date'], '%Y-%b-%d'))

    ## prepare lists of the relevant cell members
    attendees = user_data['Valid Absentees']

    ## prepare the keyboard object
    reply_keyboard = [[name] for name in attendees] + [['DONE']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    ## reply
    await update.message.reply_text(
        "<b>Okay, I've removed the member. Who else would you like to remove?</b>\n"
        f"{facts_to_str(user_data)}\n<i>Instructions: If you have finished removing, press 'DONE'.</i>",
        reply_markup=markup,
        parse_mode = 'HTML'
    )

    return REMOVING_MEMBERS_VALABSENTEES

## done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data

    ## prepare a clean attendance date
    attendance_date = datetime.strptime(user_data['Date'], '%Y-%b-%d')

    ## add attendees into the database first
    if 'Attendees' in user_data.keys():
        not_yet_added_cell_members = list(set(user_data['Attendees']) - set(db.get_alr_entered_cell_members(user_data['Cell'], attendance_date)))
        for attendee in not_yet_added_cell_members:
            db.add_attendance(user_data['Cell'], attendance_date, attendee, "Present")
        
        existing_cell_members = list(set(user_data['Attendees']).intersection(db.get_cell_members(user_data['Cell'])))
        new_cell_members = list(set(user_data['Attendees']) - set(existing_cell_members))
        for attendee in new_cell_members:
            db.add_new_member(attendee, 'New Friend', user_data['Cell'], 'None', '01-01-2000')

    ## add valid absentees into the database next
    if 'Valid Absentees' in user_data.keys():
        not_yet_added_cell_members = list(set(user_data['Valid Absentees']) - set(db.get_alr_entered_cell_members(user_data['Cell'], attendance_date)))
        for attendee in not_yet_added_cell_members:
            db.add_attendance(user_data['Cell'], attendance_date, attendee, "Absent Valid")

    ## reply
    await update.message.reply_text(
        f"<b>Thank you {update.effective_user.first_name}. As a recap, I have collected these information:</b>\n {facts_to_str(user_data)}\n<b>I have proceeded to update their attendance. Type '/start' to begin a new attendance.</b>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode = 'HTML'
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
# Create the Application and pass it your bot's token.
application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

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
                filters.Regex("^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31)$"), regular_choice_attendees
            ),
            # CommandHandler("exit", exit_),
                        ],
        CHOOSING_MEMBERS_ATTENDEES: [
            MessageHandler(
                filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$") | filters.Regex("^REMOVE$") | filters.Regex("^NONE$")), received_information_attendees
            ),
            MessageHandler(filters.Regex("^REMOVE$"), remove_attendees),
            MessageHandler(filters.Regex("^(DONE|NONE)$"), regular_choice_valabsentees),
            # CommandHandler("exit", exit_),
        ],
        REMOVING_MEMBERS_ATTENDEES: [
            MessageHandler(
                filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$")), remove_attendees_update
            ),
            MessageHandler(filters.Regex("^DONE$"), received_information_attendees),
            # CommandHandler("exit", exit_),
        ],
        CHOOSING_MEMBERS_VALABSENTEES: [
            MessageHandler(
                filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$") | filters.Regex("^REMOVE$") | filters.Regex("^NONE$")), received_information_valabsentees
            ),
            MessageHandler(filters.Regex("^REMOVE$"), remove_valabsentees),
            MessageHandler(filters.Regex("^(DONE|NONE)$"), done),
            # CommandHandler("exit", exit_),
        ],
        REMOVING_MEMBERS_VALABSENTEES: [
            MessageHandler(
                filters.TEXT & ~(filters.COMMAND | filters.Regex("^DONE$")), remove_valabsentees_update
            ),
            MessageHandler(filters.Regex("^DONE$"), received_information_valabsentees),
            # CommandHandler("exit", exit_),
        ],
    },
    fallbacks=[CommandHandler("exit", exit_)],
)


application.add_handler(conv_handler)



#######################################################################
async def tg_bot_main(application, event):
    async with application:
        await application.process_update(
            Update.de_json(json.loads(event["body"]), application.bot)
        )

def lambda_handler(event, context):
    try:
        asyncio.run(tg_bot_main(application, event))
    except Exception as e:
        traceback.print_exc()
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}