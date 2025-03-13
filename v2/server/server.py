from flask import Flask, request, jsonify
from flask.views import MethodView
from urllib.parse import quote
import requests

app = Flask(__name__)


class BaseService:
    @staticmethod
    def _handle_response(response, success_status=200):
        if response.status_code != success_status:
            return None, {"error": "Ошибка внешнего сервиса"}, 500
        try:
            return response.json(), None
        except Exception as e:
            return None, {"error": str(e)}, 500


class WeatherService(BaseService):
    API_KEY = "c2546bcfca6507032268c80b8997fb3c"
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

    def get_weather(self, **params):
        try:
            params["appid"] = self.API_KEY
            params["units"] = "metric"
            response = requests.get(self.BASE_URL, params=params)
            data, error = self._handle_response(response)
            return self._parse_data(data) if data else error
        except Exception as e:
            return {"error": str(e)}, 500

    def _parse_data(self, data):
        return {
            "city": data.get('name', 'Неизвестно'),
            "temperature": data['main'].get('temp', 'Н/Д'),
            "feels_like": data['main'].get('feels_like', 'Н/Д'),
            "humidity": data['main'].get('humidity', 'Н/Д'),
            "pressure": data['main'].get('pressure', 'Н/Д'),
            "wind_speed": data['wind'].get('speed', 'Н/Д'),
            "description": data['weather'][0].get('description', 'Н/Д') if data.get('weather') else 'Н/Д',
            "country": data['sys'].get('country', 'Н/Д')
        }


class LocationService:
    @staticmethod
    def get_by_ip():
        try:
            response = requests.get("http://ip-api.com/json")
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return data['city'], data['lat'], data['lon']
            return None, None, None
        except Exception as e:
            print(f"Ошибка определения локации: {e}")
            return None, None, None


class SearchService:
    @staticmethod
    def generate_url(base_url, query):
        return base_url.format(quote(query))

    def search_products(self, query):
        return {
            "ozon_link": self.generate_url("https://www.ozon.ru/search/?text={}", query),
            "wildberries_link": self.generate_url("https://www.wildberries.ru/catalog/0/search.aspx?search={}", query)
        }

    def search_food(self, query):
        return {
            "yandex_market_link": self.generate_url("https://market.yandex.ru/search?text={}", query),
            "sbermarket_link": self.generate_url(
                "https://kuper.ru/multisearch?q={}&shippingMethod=by_courier&sid=1&vertical=all", query)
        }

    def search_web(self, query):
        return {
            "google_link": self.generate_url("https://www.google.com/search?q={}", query),
            "yandex_link": self.generate_url("https://yandex.ru/search/?text={}", query)
        }


class FoursquareService(BaseService):
    API_KEY = "fsq3883xRYaM2mu5DbJ0Eujas7ZQwwxhqZuuBkuk5i4Yiq0="
    BASE_URL = "https://api.foursquare.com/v3/places/search"
    HEADERS = {"Authorization": API_KEY}

    def __init__(self, map_provider="google"):
        self.map_provider = map_provider

    def search_places(self, params):
        try:
            response = requests.get(self.BASE_URL, headers=self.HEADERS, params=params)
            data, error = self._handle_response(response)
            return [self._parse_place(place) for place in data.get('results', [])] if data else error
        except Exception as e:
            return {"error": str(e)}, 500

    def _parse_place(self, place):
        location = place.get('location', {})
        geocodes = place.get('geocodes', {}).get('main', {})
        return {
            "name": place.get("name", "Неизвестно"),
            "address": self._format_address(location.get("formatted_address", "")),
            "rating": place.get("rating", {}).get("score", "Н/Д"),
            "map_link": self._generate_map_link(
                geocodes.get("latitude"),
                geocodes.get("longitude"),
                self._format_address(location.get("formatted_address", ""))
            )
        }

    def _format_address(self, address):
        if isinstance(address, list):
            return ", ".join(filter(None, (part.strip() for part in address)))
        return address.strip() if address else "Адрес недоступен"

    def _generate_map_link(self, lat, lon, address=None):
        if lat and lon:
            if self.map_provider == "google":
                return f"https://www.google.com/maps?q={lat},{lon}"
            return f"https://yandex.ru/maps/?pt={lon},{lat}&z=17&l=map"

        if address:
            encoded_address = quote(address)
            if self.map_provider == "google":
                return f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
            return f"https://yandex.ru/maps/?text={encoded_address}"
        return None


class WeatherView(MethodView):
    def get(self):
        city = request.args.get('city')
        weather_service = WeatherService()
        location_service = LocationService()

        if not city:
            city, lat, lon = location_service.get_by_ip()
            if not all([city, lat, lon]):
                return jsonify({"error": "Не удалось определить локацию"}), 400
            return jsonify(weather_service.get_weather(lat=lat, lon=lon))
        return jsonify(weather_service.get_weather(q=city))


class ProductsView(MethodView):
    def get(self):
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400
        return jsonify(SearchService().search_products(query))


class FoodView(MethodView):
    def get(self):
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400
        return jsonify(SearchService().search_food(query))


class RestaurantsView(MethodView):
    def get(self):
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        map_provider = request.args.get('map_provider', 'google')

        if not all([lat, lon]):
            return jsonify({"error": "Требуются параметры lat и lon"}), 400

        service = FoursquareService(map_provider)
        return jsonify(service.search_places({
            "ll": f"{lat},{lon}",
            "categories": "13065",
            "radius": 3000,
            "limit": 10
        }))


class HotelsView(MethodView):
    def get(self):
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        map_provider = request.args.get('map_provider', 'google')

        if not all([lat, lon]):
            return jsonify({"error": "Требуются параметры lat и lon"}), 400

        service = FoursquareService(map_provider)
        return jsonify(service.search_places({
            "ll": f"{lat},{lon}",
            "categories": "19048",
            "radius": 5000,
            "limit": 10
        }))


class AddressView(MethodView):
    def get(self):
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        map_provider = request.args.get('map_provider', 'google')

        if not all([lat, lon]):
            return jsonify({"error": "Требуются параметры lat и lon"}), 400

        service = FoursquareService(map_provider)
        result = service.search_places({
            "ll": f"{lat},{lon}",
            "radius": 100,
            "limit": 1
        })
        return jsonify(result[0] if isinstance(result, list) and result else {"address": "Адрес недоступен"})


class WebSearchView(MethodView):
    def get(self):
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400
        return jsonify(SearchService().search_web(query))


class FindPlacesView(MethodView):
    def get(self):
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        query = request.args.get('query')
        map_provider = request.args.get('map_provider', 'google')

        if not all([lat, lon, query]):
            return jsonify({"error": "Требуются параметры lat, lon и query"}), 400

        service = FoursquareService(map_provider)
        return jsonify(service.search_places({
            "ll": f"{lat},{lon}",
            "query": query,
            "radius": 3000,
            "limit": 10
        }))


class SearchExactView(MethodView):
    def get(self):
        query = request.args.get('query')
        map_provider = request.args.get('map_provider', 'google')

        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400

        service = FoursquareService(map_provider)
        result = service.search_places({
            "query": query,
            "limit": 1
        })
        return jsonify(result[0] if isinstance(result, list) and result else {"error": "Место не найдено"})


app.add_url_rule('/get_weather', view_func=WeatherView.as_view('weather'))
app.add_url_rule('/search_products', view_func=ProductsView.as_view('products'))
app.add_url_rule('/search_food', view_func=FoodView.as_view('food'))
app.add_url_rule('/find_restaurants', view_func=RestaurantsView.as_view('restaurants'))
app.add_url_rule('/find_hotels', view_func=HotelsView.as_view('hotels'))
app.add_url_rule('/get_address', view_func=AddressView.as_view('address'))
app.add_url_rule('/search_web', view_func=WebSearchView.as_view('web_search'))
app.add_url_rule('/find_places', view_func=FindPlacesView.as_view('find_places'))
app.add_url_rule('/search_exact', view_func=SearchExactView.as_view('search_exact'))

if __name__ == '__main__':
    app.run(debug=True)
