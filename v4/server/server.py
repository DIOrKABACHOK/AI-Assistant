from flask import Flask, request, jsonify
from flask.views import MethodView
from flask_cors import CORS
from urllib.parse import quote
import requests
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hmac
import hashlib
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('server.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///requests.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

SECRET_KEY = "негр"
HMAC_KEY = "негр"


class VigenereCipher:
    def __init__(self, key: str):
        if not key:
            raise ValueError("Ключ не может быть пустым")
        self.key = key.lower().replace(' ', '')
        self.alphabet = 'абвгдежзийклмнопрстуфхцчшщъыьэюя0123456789.,- '
        self.char_to_index = {char: i for i, char in enumerate(self.alphabet)}

    def encrypt(self, text: str) -> str:
        encrypted = []
        key_index = 0
        for char in text.lower():
            if char in self.alphabet:
                shift = self.char_to_index[self.key[key_index % len(self.key)]]
                encrypted_char = self.alphabet[(self.char_to_index[char] + shift) % len(self.alphabet)]
                encrypted.append(encrypted_char)
                key_index += 1
            else:
                encrypted.append(char)
        return ''.join(encrypted)

    def decrypt(self, text: str) -> str:
        decrypted = []
        key_index = 0
        for char in text.lower():
            if char in self.alphabet:
                shift = self.char_to_index[self.key[key_index % len(self.key)]]
                decrypted_char = self.alphabet[(self.char_to_index[char] - shift) % len(self.alphabet)]
                decrypted.append(decrypted_char)
                key_index += 1
            else:
                decrypted.append(char)
        return ''.join(decrypted)


class RequestLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    method = db.Column(db.String(10))
    path = db.Column(db.String(255))
    request_data = db.Column(db.Text)
    response_data = db.Column(db.Text)
    status_code = db.Column(db.Integer)
    user_agent = db.Column(db.Text)
    client_ip = db.Column(db.String(45))
    user_city = db.Column(db.String(100))
    user_country = db.Column(db.String(100))
    user_id = db.Column(db.String(100))
    username = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))


@app.after_request
def log_request(response):
    try:
        user_id = request.args.get('user_id')
        username = request.args.get('username')
        first_name = request.args.get('first_name')
        last_name = request.args.get('last_name')

        data = RequestLog(
            method=request.method,
            path=request.path,
            request_data=str(request.args),
            response_data=str(response.get_data())[:500],
            status_code=response.status_code,
            user_agent=request.headers.get('User-Agent'),
            client_ip=request.remote_addr,
            user_city=request.headers.get('X-User-City', ''),
            user_country=request.headers.get('X-User-Country', ''),
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        db.session.add(data)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error logging request: {str(e)}")
    return response


class EncryptedServer:
    def __init__(self):
        self.cipher = VigenereCipher(SECRET_KEY)

    def decrypt_request(self, request):
        try:
            data = request.get_json() if request.method == 'POST' else request.args
            return {k: self.cipher.decrypt(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Ошибка дешифровки: {str(e)}")
            return None

    def encrypt_response(self, data):
        try:
            if isinstance(data, dict):
                return {k: self.cipher.encrypt(str(v)) for k, v in data.items()}
            return data
        except Exception as e:
            logger.error(f"Ошибка шифрования: {str(e)}")
            return data

    def verify_hmac(self, data, signature):
        expected_signature = hmac.new(HMAC_KEY.encode(), str(data).encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_signature, signature)


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


class WeatherView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()
        self.weather_service = WeatherService()

    def get(self):
        decrypted_params = self.encryption_handler.decrypt_request(request)
        if not decrypted_params:
            return jsonify({"error": "Ошибка дешифровки запроса"}), 400

        lat = decrypted_params.get('lat')
        lon = decrypted_params.get('lon')

        if lat and lon:
            try:
                lat = float(lat)
                lon = float(lon)
                weather_data = self.weather_service.get_weather(lat=lat, lon=lon)
            except ValueError:
                return jsonify({"error": "Неверный формат координат"}), 400
        else:
            city, lat, lon = LocationService.get_by_ip()
            if not all([lat, lon]):
                return jsonify({"error": "Не удалось определить локацию"}), 400
            weather_data = self.weather_service.get_weather(lat=lat, lon=lon)

        return jsonify(self.encryption_handler.encrypt_response(weather_data))


class LocationService:
    GEOCODING_URL = "http://api.openweathermap.org/geo/1.0/direct"

    @classmethod
    def get_by_ip(cls):
        try:
            response = requests.get("http://ip-api.com/json")
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return data['city'], data['lat'], data['lon']
            return None, None, None
        except Exception as e:
            logger.error(f"Ошибка определения локации: {e}")
            return None, None, None

    @classmethod
    def geocode_address(cls, address):
        try:
            response = requests.get(cls.GEOCODING_URL, params={
                'q': address,
                'limit': 1,
                'appid': WeatherService.API_KEY
            })
            if response.status_code == 200:
                data = response.json()
                if data:
                    return data[0]['name'], data[0]['lat'], data[0]['lon']
            return None, None, None
        except Exception as e:
            logger.error(f"Ошибка геокодирования: {e}")
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


class ProductsView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()
        self.search_service = SearchService()

    def get(self):
        decrypted_params = self.encryption_handler.decrypt_request(request)
        if not decrypted_params:
            return jsonify({"error": "Ошибка дешифровки запроса"}), 400

        query = decrypted_params.get('query')
        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400
        return jsonify(self.encryption_handler.encrypt_response(self.search_service.search_products(query)))


class FoodView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()
        self.search_service = SearchService()

    def get(self):
        decrypted_params = self.encryption_handler.decrypt_request(request)
        if not decrypted_params:
            return jsonify({"error": "Ошибка дешифровки запроса"}), 400

        query = decrypted_params.get('query')
        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400
        return jsonify(self.encryption_handler.encrypt_response(self.search_service.search_food(query)))


class RestaurantsView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()

    def get(self):
        try:
            decrypted_params = self.encryption_handler.decrypt_request(request)
            if not decrypted_params:
                return jsonify({"error": "Ошибка дешифровки запроса"}), 400

            lat = decrypted_params.get('lat')
            lon = decrypted_params.get('lon')

            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                city, lat, lon = LocationService.get_by_ip()
                if not all([lat, lon]):
                    return jsonify({"error": "Не удалось определить местоположение"}), 400

            service = FoursquareService('google')
            result = service.search_places({
                "ll": f"{lat},{lon}",
                "categories": "13065",
                "radius": 3000,
                "limit": 10
            })

            return jsonify(self.encryption_handler.encrypt_response(result))
        except Exception as e:
            logger.error(f"Ошибка в RestaurantsView: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500


class HotelsView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()

    def get(self):
        try:
            decrypted_params = self.encryption_handler.decrypt_request(request)
            if not decrypted_params:
                return jsonify({"error": "Ошибка дешифровки запроса"}), 400

            lat = decrypted_params.get('lat')
            lon = decrypted_params.get('lon')

            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                city, lat, lon = LocationService.get_by_ip()
                if not all([lat, lon]):
                    return jsonify({"error": "Не удалось определить местоположение"}), 400

            service = FoursquareService('google')
            result = service.search_places({
                "ll": f"{lat},{lon}",
                "categories": "19048",
                "radius": 5000,
                "limit": 10
            })

            return jsonify(self.encryption_handler.encrypt_response(result))
        except Exception as e:
            logger.error(f"Ошибка в HotelsView: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500


class AddressView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()

    def get(self):
        try:
            decrypted_params = self.encryption_handler.decrypt_request(request)
            if not decrypted_params:
                return jsonify({"error": "Ошибка дешифровки запроса"}), 400

            lat = decrypted_params.get('lat')
            lon = decrypted_params.get('lon')

            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                city, lat, lon = LocationService.get_by_ip()
                if not all([lat, lon]):
                    return jsonify({"error": "Не удалось определить местоположение"}), 400

            service = FoursquareService('google')
            result = service.search_places({
                "ll": f"{lat},{lon}",
                "radius": 100,
                "limit": 1
            })
            return jsonify(self.encryption_handler.encrypt_response(
                result[0] if isinstance(result, list) and result else {"address": "Адрес недоступен"}
            ))
        except Exception as e:
            logger.error(f"Ошибка в AddressView: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500


class WebSearchView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()
        self.search_service = SearchService()

    def get(self):
        decrypted_params = self.encryption_handler.decrypt_request(request)
        if not decrypted_params:
            return jsonify({"error": "Ошибка дешифровки запроса"}), 400

        query = decrypted_params.get('query')
        if not query:
            return jsonify({"error": "Необходим параметр query"}), 400
        return jsonify(self.encryption_handler.encrypt_response(self.search_service.search_web(query)))


class FindPlacesView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()

    def get(self):
        try:
            decrypted_params = self.encryption_handler.decrypt_request(request)
            if not decrypted_params:
                return jsonify({"error": "Ошибка дешифровки запроса"}), 400

            lat = decrypted_params.get('lat')
            lon = decrypted_params.get('lon')
            query = decrypted_params.get('query')

            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                city, lat, lon = LocationService.get_by_ip()
                if not all([lat, lon]):
                    return jsonify({"error": "Не удалось определить местоположение"}), 400

            service = FoursquareService('google')
            result = service.search_places({
                "ll": f"{lat},{lon}",
                "query": query,
                "radius": 3000,
                "limit": 10
            })

            return jsonify(self.encryption_handler.encrypt_response(result))
        except Exception as e:
            logger.error(f"Ошибка в FindPlacesView: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500


class SearchExactView(MethodView):
    def __init__(self):
        self.encryption_handler = EncryptedServer()

    def get(self):
        try:
            decrypted_params = self.encryption_handler.decrypt_request(request)
            if not decrypted_params:
                return jsonify({"error": "Ошибка дешифровки запроса"}), 400

            query = decrypted_params.get('query')
            if not query:
                return jsonify({"error": "Необходим параметр query"}), 400

            service = FoursquareService('google')
            result = service.search_places({
                "query": query,
                "limit": 1
            })
            return jsonify(self.encryption_handler.encrypt_response(
                result[0] if isinstance(result, list) and result else {"error": "Место не найдено"}
            ))
        except Exception as e:
            logger.error(f"Ошибка в SearchExactView: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500


app.add_url_rule('/get_weather', view_func=WeatherView.as_view('weather'))
app.add_url_rule('/search_products', view_func=ProductsView.as_view('products'))
app.add_url_rule('/search_food', view_func=FoodView.as_view('food'))
app.add_url_rule('/find_restaurants', view_func=RestaurantsView.as_view('restaurants'))
app.add_url_rule('/find_hotels', view_func=HotelsView.as_view('hotels'))
app.add_url_rule('/get_address', view_func=AddressView.as_view('address'))
app.add_url_rule('/search_web', view_func=WebSearchView.as_view('web_search'))
app.add_url_rule('/find_places', view_func=FindPlacesView.as_view('find_places'))
app.add_url_rule('/search_exact', view_func=SearchExactView.as_view('search_exact'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
