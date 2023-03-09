import datetime
import logging
from flight_search import FlightSearch
from telebot import TeleBot
from telebot import types
from telegram_bot_calendar import LSTEP, WMonthTelegramCalendar
from flight_data import FlightRequestData
import os
from dotenv import load_dotenv
import geonamescache

load_dotenv(verbose=True)

# Logging config
logging.basicConfig(level=logging.INFO)

# Initialize bot
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
bot = TeleBot(BOT_TOKEN)
bot.set_my_commands([
    types.BotCommand("/start", "search flights")
])

# Initialize dates, format ex.: 09/01/2023
tomorrow_date = (datetime.date.today() + datetime.timedelta(days=1))
six_months_date = (datetime.date.today() + datetime.timedelta(days=180))

# Initialize geonamescache to get all city names
gc = geonamescache.GeonamesCache()

# Initialize flight search and request data classes
flight_search = FlightSearch()
flight_req_data = FlightRequestData()

# Start bot
@bot.message_handler(commands=['start'])
def message_handler(message, invalid_cities=False, error_message=''):
    logging.info("Bot initiated")
    msg = bot.send_message(message.chat.id,
                           f"Which cities are you flying to?\nSpecify cities divided by slash")
    if invalid_cities:
        bot.edit_message_text(f"{error_message}. Please specify cities divided by slash."
                              f"\nExample: Paris/Vienna", msg.chat.id, msg.message_id)
    bot.register_next_step_handler(msg, get_departure_date)


# Bot callbacks
@bot.callback_query_handler(func=WMonthTelegramCalendar.func())
def next_page(call):
    result, key, step = WMonthTelegramCalendar(min_date=tomorrow_date, max_date=six_months_date).process(call.data)
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
        flight_req_data.is_other = True
        specify_stay_range(call.message)
        bot.register_next_step_handler(call.message, send_flight_details)

    if flight_req_data.flight_type and flight_req_data.duration_of_stay and call.data != 'other':
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
    markup.add(types.InlineKeyboardButton("Specify duration of stay", callback_data="other"))
    return markup


def search_flight(fly_from, fly_to, flight_type, duration, departure_date):
    if flight_type == "round":
        flight = flight_search.search_round_flights(fly_from=fly_from,
                                                    fly_to=fly_to,
                                                    date_from=departure_date,
                                                    date_to=six_months_date.strftime("%d/%m/%Y"),
                                                    nights_in_dst_from=duration,
                                                    nights_in_dst_to=duration,
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
                                                     date_to=six_months_date.strftime("%d/%m/%Y"),
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
    bot.send_message(message.chat.id, "Oneway or round trip?",
                     reply_markup=gen_markup_flight_type())


def get_departure_date(message):
    # TODO: add regex check
    error_message = ''
    if '/' not in message.text:
        error_message = "Wrong format"
    elif message.text.split('/')[1] == '':
        error_message = "Arrival city required"
    elif not gc.get_cities_by_name(message.text.split('/')[0].lower().title()):
        error_message = "Invalid departure city"
    elif not gc.get_cities_by_name(message.text.split('/')[1].lower().title()):
        error_message = "Invalid arrival city"

    if error_message:
        logging.warning(f"{message.from_user.username} requested wrong city pairs: {message.text}. {error_message}")
        message_handler(message, True, error_message=error_message)
    else:
        flight_req_data.city_pairs = message.text
        flight_req_data.username = message.from_user.username
        calendar, step = WMonthTelegramCalendar().build()
        bot.send_message(message.chat.id,
                         f"Select earliest departure {LSTEP[step]}",
                         reply_markup=calendar)


def get_duration_of_stay(message):
    bot.send_message(message.chat.id, "How many days to stay?",
                     reply_markup=gen_markup_duration_of_stay())


def specify_stay_range(message, invalid_duration=False):
    if invalid_duration:
        bot.send_message(message.chat.id, "Specify a valid number of days, up to 180 days. Example: 10")
        bot.register_next_step_handler(message, send_flight_details)
    else:
        bot.send_message(message.chat.id, "Specify number of days")


def send_flight_details(message):
    try:
        if flight_req_data.is_other:
            flight_req_data.duration_of_stay = int(message.text)
            if flight_req_data.duration_of_stay > 180:
                logging.info(f"Value error when setting duration of stay, duration more than 180 days:"
                             f" {flight_req_data.duration_of_stay}")
                raise ValueError
    except ValueError:
        logging.info(f"Value error when setting duration of stay: {flight_req_data.duration_of_stay}")
        specify_stay_range(message, True)
    else:
        flight_req_data.is_other = False
        iata_code_from = flight_search.get_iata_code(city=flight_req_data.city_pairs.split('/')[0])
        iata_code_to = flight_search.get_iata_code(city=flight_req_data.city_pairs.split('/')[1])

        logging.info(f"{flight_req_data.username} requested {flight_req_data.flight_type} flight from"
                     f" {iata_code_from} to {iata_code_to}")

        bot.send_message(message.chat.id, search_flight(fly_from=iata_code_from.strip(),
                                                        fly_to=iata_code_to.strip(),
                                                        departure_date=flight_req_data.departure_date,
                                                        flight_type=flight_req_data.flight_type,
                                                        duration=flight_req_data.duration_of_stay)
                         , parse_mode="Markdown")
        flight_req_data.duration_of_stay = 0


bot.infinity_polling()
