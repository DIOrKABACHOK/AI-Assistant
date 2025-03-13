from flask import Flask, request, jsonify
from flask.views import MethodView
from urllib.parse import quote
import requests

app = Flask(__name__)


class WeatherService:
    WEATHER_API_KEY = "c2546bcfca6507032268c80b8997fb3c"

    def get_weather_by_city(self, city):
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.WEATHER_API_KEY}&units=metric"
        return self._fetch_weather_data(url)

    def get_weather_by_coordinates(self, latitude, longitude):
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={self.WEATHER_API_KEY}&units=metric"
        return self._fetch_weather_data(url)

    def _fetch_weather_data(self, url):
        try:
            response = requests.get(url)
            if response.status_code != 200:
                return {"error": "Failed to fetch weather data"}, 500
            weather_data = response.json()
            return {
                "city": weather_data.get('name', 'Unknown'),
                "temperature": weather_data['main'].get('temp', 'N/A'),
                "feels_like": weather_data['main'].get('feels_like', 'N/A'),
                "humidity": weather_data['main'].get('humidity', 'N/A'),
                "pressure": weather_data['main'].get('pressure', 'N/A'),
                "wind_speed": weather_data['wind'].get('speed', 'N/A'),
                "description": weather_data['weather'][0].get('description', 'N/A'),
                "country": weather_data['sys'].get('country', 'N/A')
            }
        except Exception as e:
            return {"error": str(e)}, 500


class LocationService:
    def get_location_by_ip(self):
        try:
            response = requests.get("http://ip-api.com/json")
            data = response.json()
            if data['status'] == 'success':
                return data['city'], data['lat'], data['lon']
            return None, None, None
        except Exception as e:
            print("Ошибка при получении данных по IP:", e)
            return None, None, None


class SearchService:
    def search_products(self, query):
        encoded_query = quote(query)
        ozon_url = f"https://www.ozon.ru/search/?text={encoded_query}"
        wildberries_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_query}"
        return {
            "ozon_link": ozon_url,
            "wildberries_link": wildberries_url
        }

    def search_food(self, query):
        encoded_query = quote(query)
        yandex_market_url = f"https://market.yandex.ru/search?text={encoded_query}"
        sbermarket_url = (
            f"https://kuper.ru/multisearch?"
            f"q={encoded_query}&"
            f"shippingMethod=by_courier&"
            f"sid=1&"
            f"vertical=all"
        )
        return {
            "yandex_market_link": yandex_market_url,
            "sbermarket_link": sbermarket_url
        }

    def search_web(self, query):
        encoded_query = quote(query)
        google_url = f"https://www.google.com/search?q={encoded_query}"
        yandex_url = f"https://yandex.ru/search/?text={encoded_query}"
        return {
            "google_link": google_url,
            "yandex_link": yandex_url
        }


class FoursquareService:
    FOURSQUARE_API_KEY = "fsq3883xRYaM2mu5DbJ0Eujas7ZQwwxhqZuuBkuk5i4Yiq0="

    def __init__(self, map_provider="google"):
        self.map_provider = map_provider

    def find_restaurants(self, latitude, longitude):
        return self._find_places(latitude, longitude, "13065", "Restaurant")

    def find_hotels(self, latitude, longitude):
        return self._find_places(latitude, longitude, "19048", "Hotel")

    def get_address(self, latitude, longitude):
        url = "https://api.foursquare.com/v3/places/search"
        headers = {"Authorization": self.FOURSQUARE_API_KEY}
        params = {"ll": f"{latitude},{longitude}", "radius": 100, "limit": 1}
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                return {"address": "Address not available"}
            places_data = response.json()
            results = places_data.get("results", [])
            if not results:
                return {"address": "Address not available"}
            place = results[0]
            address_parts = place.get("location", {}).get("formatted_address", [])
            address = self._format_address(address_parts)
            lat = place.get("geocodes", {}).get("main", {}).get("latitude")
            lon = place.get("geocodes", {}).get("main", {}).get("longitude")
            return {
                "address": address,
                "map_link": self._generate_map_link(lat, lon, address)
            }
        except Exception as e:
            return {"error": str(e)}

    def _find_places(self, latitude, longitude, category, description):
        url = "https://api.foursquare.com/v3/places/search"
        headers = {"Authorization": self.FOURSQUARE_API_KEY}
        params = {
            "ll": f"{latitude},{longitude}",
            "radius": 3000 if description == "Restaurant" else 5000,
            "categories": category,
            "limit": 10
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                return {"error": "Failed to fetch place data"}, 500
            places_data = response.json()
            places = []
            for place in places_data.get("results", []):
                address_parts = place.get("location", {}).get("formatted_address", [])
                address = self._format_address(address_parts)
                lat = place.get("geocodes", {}).get("main", {}).get("latitude")
                lon = place.get("geocodes", {}).get("main", {}).get("longitude")
                places.append({
                    "name": place.get("name", "Unknown"),
                    "address": address,
                    "description": description,
                    "rating": place.get("rating", {}).get("score", "N/A"),
                    "map_link": self._generate_map_link(lat, lon, address)
                })
            return places
        except Exception as e:
            return {"error": str(e)}, 500

    def _format_address(self, address_parts):
        if not address_parts:
            return "Address not available"
        if isinstance(address_parts, list):
            cleaned_address = "".join([part.strip() for part in address_parts if part.strip()])
        elif isinstance(address_parts, str):
            cleaned_address = address_parts.strip()
        else:
            return "Address not available"
        cleaned_address = ", ".join([part.strip() for part in cleaned_address.split(",") if part.strip()])
        return cleaned_address

    def _generate_map_link(self, lat, lon, address=None, map_provider=None):
        provider = map_provider or self.map_provider
        if lat and lon:
            if provider == "google":
                return f"https://www.google.com/maps?q={lat},{lon}"
            elif provider == "yandex":
                return f"https://yandex.ru/maps/?pt={lon},{lat}&z=17&l=map"
        elif address:
            if provider == "google":
                return f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
            elif provider == "yandex":
                return f"https://yandex.ru/maps/?text={address.replace(' ', '+')}"
        return None


class WeatherView(MethodView):
    def get(self):
        city = request.args.get('city')
        weather_service = WeatherService()
        if not city:
            location_service = LocationService()
            city, latitude, longitude = location_service.get_location_by_ip()
            if not city or not latitude or not longitude:
                return jsonify({"error": "Failed to determine location"}), 400
            weather_data = weather_service.get_weather_by_coordinates(latitude, longitude)
        else:
            weather_data = weather_service.get_weather_by_city(city)
        return jsonify(weather_data)


class ProductsView(MethodView):
    def get(self):
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        search_service = SearchService()
        return jsonify(search_service.search_products(query))


class FoodView(MethodView):
    def get(self):
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        search_service = SearchService()
        return jsonify(search_service.search_food(query))


class RestaurantsView(MethodView):
    def get(self):
        latitude = request.args.get('lat')
        longitude = request.args.get('lon')
        map_provider = request.args.get('map_provider', 'google')
        if not latitude or not longitude:
            return jsonify({"error": "Latitude and Longitude are required"}), 400
        foursquare_service = FoursquareService(map_provider)
        return jsonify(foursquare_service.find_restaurants(latitude, longitude))


class HotelsView(MethodView):
    def get(self):
        latitude = request.args.get('lat')
        longitude = request.args.get('lon')
        map_provider = request.args.get('map_provider', 'google')
        if not latitude or not longitude:
            return jsonify({"error": "Latitude and Longitude are required"}), 400
        foursquare_service = FoursquareService(map_provider)
        return jsonify(foursquare_service.find_hotels(latitude, longitude))


class AddressView(MethodView):
    def get(self):
        latitude = request.args.get('lat')
        longitude = request.args.get('lon')
        map_provider = request.args.get('map_provider', 'google')
        if not latitude or not longitude:
            return jsonify({"error": "Latitude and Longitude are required"}), 400
        foursquare_service = FoursquareService(map_provider)
        return jsonify(foursquare_service.get_address(latitude, longitude))


class WebSearchView(MethodView):
    def get(self):
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        search_service = SearchService()
        return jsonify(search_service.search_web(query))


class FindPlacesView(MethodView):
    def get(self):
        latitude = request.args.get('lat')
        longitude = request.args.get('lon')
        query = request.args.get('query')
        map_provider = request.args.get('map_provider', 'google')

        if not all([latitude, longitude, query]):
            return jsonify({"error": "Latitude, Longitude, and Query are required"}), 400

        foursquare_service = FoursquareService(map_provider)
        url = "https://api.foursquare.com/v3/places/search"
        headers = {"Authorization": foursquare_service.FOURSQUARE_API_KEY}
        params = {
            "ll": f"{latitude},{longitude}",
            "radius": 3000,
            "query": query,
            "limit": 10
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                return jsonify({"error": "Failed to fetch places data"}), 500

            places_data = response.json()
            places = []
            for place in places_data.get("results", []):
                address_parts = place.get("location", {}).get("formatted_address", [])
                address = foursquare_service._format_address(address_parts)
                lat = place.get("geocodes", {}).get("main", {}).get("latitude")
                lon = place.get("geocodes", {}).get("main", {}).get("longitude")
                places.append({
                    "name": place.get("name", "Unknown"),
                    "address": address,
                    "map_link": foursquare_service._generate_map_link(lat, lon, address)
                })
            return jsonify(places)
        except Exception as e:
            return jsonify({"error": str(e)}), 500


class SearchExactView(MethodView):
    def get(self):
        query = request.args.get('query')
        map_provider = request.args.get('map_provider', 'google')

        if not query:
            return jsonify({"error": "Query parameter is required"}), 400

        foursquare_service = FoursquareService(map_provider)
        url = "https://api.foursquare.com/v3/places/search"
        headers = {"Authorization": foursquare_service.FOURSQUARE_API_KEY}
        params = {
            "query": query,
            "limit": 1
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                return jsonify({"error": "Failed to fetch place data"}), 500

            places_data = response.json()
            results = places_data.get("results", [])
            if not results:
                return jsonify({"error": "Place not found"}), 404

            place = results[0]
            address_parts = place.get("location", {}).get("formatted_address", [])
            address = foursquare_service._format_address(address_parts)
            lat = place.get("geocodes", {}).get("main", {}).get("latitude")
            lon = place.get("geocodes", {}).get("main", {}).get("longitude")

            return jsonify({
                "name": place.get("name", "Unknown"),
                "address": address,
                "map_link": foursquare_service._generate_map_link(lat, lon, address=address, map_provider=map_provider)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


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
