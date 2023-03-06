from dataclasses import dataclass


class FlightResponseData:

    def __init__(self, price, origin_city, origin_airport, destination_city, destination_airport, out_date,
                 link, return_date=0):
        self.price = price
        self.origin_city = origin_city
        self.origin_airport = origin_airport
        self.destination_city = destination_city
        self.destination_airport = destination_airport
        self.out_date = out_date
        self.return_date = return_date
        self.link = link


@dataclass
class FlightRequestData:
    duration_of_stay: int = 0
    city_pairs: str = ""
    flight_type: str = ""
    duration_of_stay: str = ""
