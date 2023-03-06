import datetime

from flight_search import FlightSearch
from telebot import TeleBot
from telebot import types
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from flight_data import FlightRequestData
import os
from dotenv import load_dotenv
load_dotenv(verbose=True)

# Initialize bot
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
bot = TeleBot(BOT_TOKEN)
bot.set_my_commands([
    types.BotCommand("/start", "search flights")
])

# Initialize dates, format ex.: 09/01/2023
tomorrow_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%d/%m/%Y")
six_months_date = (datetime.date.today() + datetime.timedelta(days=180)).strftime("%d/%m/%Y")

# Initialize flight search and request data classes
flight_search = FlightSearch()
flight_req_data = FlightRequestData()


# Start bot
@bot.message_handler(commands=['start'])
def message_handler(message):
    msg = bot.send_message(message.chat.id,
                           f"Which cities are you flying to?\nSpecify the cities divided by slash")
    bot.register_next_step_handler(msg, get_departure_date)


# Bot callbacks
@bot.callback_query_handler(func=DetailedTelegramCalendar.func())
def next_page(call):
    print("calendar callback")
    result, key, step = DetailedTelegramCalendar().process(call.data)
    m = call.message

    if not result and key:
        bot.edit_message_text(f"Select {LSTEP[step]}", m.chat.id, m.message_id, reply_markup=key)
    elif result:
        bot.edit_message_text(f"You selected {result}", m.chat.id, m.message_id)
        flight_req_data.departure_date = result.strftime("%d/%m/%Y")
        get_flight_type(m)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    flight_req_data.flight_type = "oneway" if call.data == "oneway" else "round"
    if call.data == "round":
        get_duration_of_stay(call.message)
    if call.data == "oneway":
        flight_req_data.duration_of_stay = 1
    if call.data == "3_days":
        flight_req_data.duration_of_stay = 3
    if call.data == "7_days":
        flight_req_data.duration_of_stay = 7
    if call.data == "other":
        specify_stay_range(call.message)
        bot.register_next_step_handler(call.message, send_flight_details)

    if flight_req_data.flight_type and flight_req_data.duration_of_stay != 0 and call.data != 'other':
        send_flight_details(call.message)


# Generate markups
def gen_markup_flight_type():
    markup = types.InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(types.InlineKeyboardButton("Oneway", callback_data="oneway"))
    markup.add(types.InlineKeyboardButton("Round", callback_data="round"))
    return markup


def gen_markup_duration_of_stay():
    markup = types.InlineKeyboardMarkup()
    markup.row_width = 3
    markup.add(types.InlineKeyboardButton("3 days", callback_data="3_days"))
    markup.add(types.InlineKeyboardButton("7 days", callback_data="7_days"))
    markup.add(types.InlineKeyboardButton("Other", callback_data="other"))
    return markup


def search_flight(fly_from, fly_to, flight_type, duration, departure_date):
    if flight_type == "round":
        flight = flight_search.search_round_flights(fly_from=fly_from,
                                                    fly_to=fly_to,
                                                    date_from=departure_date,
                                                    date_to=six_months_date,
                                                    nights_in_dst_from=duration[0],
                                                    nights_in_dst_to=duration[1],
                                                    flight_type=flight_type,
                                                    vehicle_type="aircraft",
                                                    max_stopovers=0,
                                                    limit=10)
        if flight is not None:
            return f"{flight.destination_city}: €{flight.price}\n" \
                   f"Departure date: {flight.out_date}\n" \
                   f"Return date: {flight.return_date}\n" \
                   f"[Link]({flight.link})"
        else:
            return f"No flights found for {fly_from}/{fly_to}."
    else:
        flight = flight_search.search_oneway_flights(fly_from=fly_from,
                                                     fly_to=fly_to,
                                                     date_from=departure_date,
                                                     date_to=six_months_date,
                                                     flight_type=flight_req_data.flight_type,
                                                     vehicle_type="aircraft",
                                                     max_stopovers=0,
                                                     limit=10)
        if flight is not None:
            return f"{flight.destination_city}: €{flight.price}\n" \
                   f"Departure date: {flight.out_date}\n" \
                   f"[Link]({flight.link})"
        else:
            return f"No flights found for {fly_from}/{fly_to}."


def get_flight_type(message):
    print("step 1")
    bot.send_message(message.chat.id, "Oneway or round trip?",
                     reply_markup=gen_markup_flight_type())
    print(f"city pairs: {flight_req_data.city_pairs}")


def get_departure_date(message):
    calendar, step = DetailedTelegramCalendar().build()
    bot.send_message(message.chat.id,
                     f"Select {LSTEP[step]}",
                     reply_markup=calendar)
    flight_req_data.city_pairs = message.text


def get_duration_of_stay(message):
    print("step 2")
    bot.send_message(message.chat.id, "How many days to stay?",
                     reply_markup=gen_markup_duration_of_stay())


def specify_stay_range(message):
    print("additional step")
    bot.send_message(message.chat.id,
                     "Specify stay range divided by dash\nExample: 3-5 (between 3 and 5 days)")


def send_flight_details(message):
    if '-' in message.text:
        duration_of_stay_list = [int(x) for x in message.text.split("-")]
    else:
        duration_of_stay_list = [flight_req_data.duration_of_stay, flight_req_data.duration_of_stay]

    iata_code_from = flight_search.get_iata_code(city=flight_req_data.city_pairs.split('/')[0])
    iata_code_to = flight_search.get_iata_code(city=flight_req_data.city_pairs.split('/')[1])
    bot.send_message(message.chat.id, search_flight(fly_from=iata_code_from.strip(),
                                                    fly_to=iata_code_to.strip(),
                                                    departure_date=flight_req_data.departure_date,
                                                    flight_type=flight_req_data.flight_type,
                                                    duration=duration_of_stay_list)
                     , parse_mode="Markdown")
    flight_req_data.duration_of_stay = 0


bot.infinity_polling()

# TODO: Use flight_data object instead of ugly globals DONE
# TODO: Add filtering by from/todate: Added filtering fromdate via calendar, not sure about todate now
# TODO: Add filtering by airline: not sure if necessary?
# TODO: Add dotenv to store secrets in .env DONE
# TODO: Update with docustirng and add read.me (try using chatgpt to generate documentation)
