import requests
import logging
from flight_data import FlightResponseData
import os
from dotenv import load_dotenv
load_dotenv(verbose=True)

FLIGHT_LOCATION_URL = "https://api.tequila.kiwi.com/locations/query"
FLIGHT_SEARCH_URL = "https://api.tequila.kiwi.com/v2/search"
FLIGHT_API_KEY = os.getenv("FLIGHT_API_KEY")


class FlightSearch:

    def get_iata_code(self, city):
        headers = {
            "apikey": FLIGHT_API_KEY
        }

        params = {
            "term": city,
            "location_types": "city"
        }

        response = requests.get(url=FLIGHT_LOCATION_URL, headers=headers, params=params)
        return response.json()["locations"][0]['code']

    def search_round_flights(self, **kwargs):
        headers = {
            "apikey": FLIGHT_API_KEY
        }
        params = {}
        for key, value in kwargs.items():
            params[key] = value

        response = requests.get(url=FLIGHT_SEARCH_URL, headers=headers, params=params)
        try:
            data = response.json()["data"][0]
        except IndexError:
            print(f"No flights found for {kwargs['fly_from']}.")
            logging.info(f"No flights found for {kwargs['fly_from']}.")
            return None
        except KeyError:
            logging.info(f"Invalid data key in response: {response.json()}")

        flight_data = FlightResponseData(
            price=data["price"],
            origin_city=data["route"][0]["cityFrom"],
            origin_airport=data["route"][0]["flyFrom"],
            destination_city=data["route"][0]["cityTo"],
            destination_airport=data["route"][0]["flyTo"],
            out_date=data["route"][0]["local_departure"].split("T")[0],
            return_date=data["route"][1]["local_departure"].split("T")[0],
            link=data["deep_link"]
        )
        return flight_data

    def search_oneway_flights(self, **kwargs):
        headers = {
            "apikey": FLIGHT_API_KEY
        }
        params = {}
        for key, value in kwargs.items():
            params[key] = value

        response = requests.get(url=FLIGHT_SEARCH_URL, headers=headers, params=params)
        try:
            data = response.json()["data"][0]
        except IndexError:
            print(f"No flights found for {kwargs['fly_from']}/{kwargs['fly_to']}.")
            logging.info(f"No flights found for {kwargs['fly_from']}//{kwargs['fly_to']}.")
            return None

        flight_data = FlightResponseData(
            price=data["price"],
            origin_city=data["route"][0]["cityFrom"],
            origin_airport=data["route"][0]["flyFrom"],
            destination_city=data["route"][0]["cityTo"],
            destination_airport=data["route"][0]["flyTo"],
            out_date=data["route"][0]["local_departure"].split("T")[0],
            link=data["deep_link"]
        )

        return flight_data
