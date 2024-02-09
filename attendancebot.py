# 1. Library imports
import requests
import json
import time
import urllib
import creds
# from bobbycxyTest2_1_dbhelper import DBHelper
from dynamodbhelperv1 import DynamoDBHelper
db = DynamoDBHelper()


# 2. Key Variables
TOKEN = creds.TELEGRAM_TOKEN
URL = 'https://api.telegram.org/bot' + TOKEN + '/'



# 3. Creation of Functions
def get_url(url):
    '''To execute our url, and then return our results in a string'''
    response = requests.get(url)
    content = response.content.decode('utf-8')
    return content

def get_json_from_url(url):
    '''converts the string result of get_url into a python dictionary'''
    content = get_url(url)
    js = json.loads(content)
    return js

def get_updates(offset = None):
    url = URL + 'getUpdates?timeout=100'
    if offset:
        url += '&offset={}'.format(offset)
    js = get_json_from_url(url)
    return js

def get_last_chat_id_and_text(updates):
    text = get_updates()['result'][-1]['message']['text']
    chat_id = get_updates()['result'][-1]['message']['chat']['id']
    return text, chat_id

def send_message(text, chat_id, reply_markup=None):
    text = urllib.parse.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(text, chat_id)
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    get_url(url)

# this to get the latest set of update upon us sending out a bunch of messages

def get_latest_update_id(updates):
    update_ids = []
    for update in updates['result']:
        update_ids.append(int(update['update_id']))
    return max(update_ids)

# at this step, we'll be retiring the echo_all function in place of a new function called
# 'handle_updates'

# def echo_all(updates):
#     for update in updates['result']:
#         try:
#             text = update['message']['text']
#             chat_id = update['message']['chat']['id']
#             send_message(text, chat_id)
#         except Exception as e:
#             print(e)

def build_keyboard(items):
    keyboard = [[item] for item in items]
    reply_markup = {'keyboard': keyboard, 'one_time_keyboard': True}
    return json.dumps(reply_markup)


def handle_updates(updates, cell_group, cell_members, date_attended):

    for update in updates['result']:
        try:
            text = update['message']['text']
            chat_id = update['message']['chat']['id']
            
            cell_groups = db.get_cell_groups()
            attendend_cell_members = db.get_alr_attended_cell_members(cell_group, date_attended)

            if text == '/start':
                send_message("Hi, this is an attendance bot for POD Youths. Begin by selecting the cell group you are in.", chat_id, build_keyboard(cell_groups))
            elif text == '/done':
                send_message("You've taken attendance for {} for {}. They are {}.".format(cell_group, date_attended, ', '.join(attendend_cell_members)), chat_id)
            elif text in cell_groups:
                cell_group = text
                send_message("You're taking attendance for {}. Now enter the date (dd/mm/yy) you are taking for.".format(cell_group), chat_id)
            elif '/' in text:
                date_attended = text
                print(cell_group)
                cell_members = db.get_cell_members(cell_group)
                attendend_cell_members = db.get_alr_attended_cell_members(cell_group, date_attended)
                relevant_cell_members = list(set(cell_members) - set(attendend_cell_members))
                print(cell_members)
                send_message("You're taking attendance for {} for {}. Feel free to select any members from the undermentioned keyboard.".format(cell_group, date_attended), chat_id, build_keyboard(relevant_cell_members))
            elif cell_members:
                if text in cell_members:
                    name = text
                    db.add_attendance(cell_group, date_attended, name)
                    cell_members = db.get_cell_members(cell_group)
                    attendend_cell_members = db.get_alr_attended_cell_members(cell_group, date_attended)
                    relevant_cell_members = list(set(cell_members) - set(attendend_cell_members))
                    send_message("You're taking attendance for {} for {}. You've keyed in for {} so far. Send /done when you're finished.".format(cell_group, date_attended, ', '.join(attendend_cell_members)), chat_id, build_keyboard(relevant_cell_members))
            else:
                send_message(text, chat_id)
        except KeyError:
            pass

    print(cell_group, cell_members, date_attended)
    return cell_group, cell_members, date_attended













# def handle_updates(updates):
#     for update in updates['result']:
#         try:
#             text = update['message']['text']
#             chat_id = update['message']['chat']['id']
#             items = db.get_items(chat_id)
#             if text == "/done":
#                 keyboard = build_keyboard(items)
#                 send_message("Select an item to delete", chat_id, keyboard)
#             elif text == '/start':
#                 send_message("Welcome to your personal To Do list. Send any text to me and I'll store it as an item. Send /done to remove items", chat_id)
#             elif text.startswith('/'):
#                 continue
#             elif text in items:
#                 db.delete_item(text, chat_id)
#                 items = db.get_items(chat_id)
#                 keyboard = build_keyboard(items)
#                 if len(items) == 0:
#                     send_message("You have no more reminders! Way to go for clearing them all!", chat_id)
#                 else:
#                     send_message("Select an item to delete", chat_id, keyboard)
#             else:
#                 db.add_item(text, chat_id)
#                 items = db.get_items(chat_id)
#                 message = "\n".join(items)
#                 send_message(message, chat_id)
#         except KeyError:
#             pass

def main():
    db.setup()
    last_update_id = None

    cell_group = None
    cell_members = None
    date_attended = None

    while True:
        updates = get_updates(last_update_id)
        if len(updates['result']) > 0 :
            last_update_id = get_latest_update_id(updates) + 1
            cell_group, cell_members, date_attended = handle_updates(updates, cell_group, cell_members, date_attended)
        time.sleep(0.5)

if __name__ == '__main__':
    main()
