import requests


class WeatherClient:
    BASE_URL = "http://127.0.0.1:5000/get_weather"

    def get_weather(self, city=None):
        params = {"city": city} if city else {}
        response = requests.get(self.BASE_URL, params=params)
        if response.status_code == 200:
            weather = response.json()
            print(f"Погода в {weather['city']}, {weather['country']}:")
            print(f"- Температура: {weather['temperature']}°C")
            print(f"- Ощущается как: {weather['feels_like']}°C")
            print(f"- Влажность: {weather['humidity']}%")
            print(f"- Давление: {weather['pressure']} hPa")
            print(f"- Скорость ветра: {weather['wind_speed']} м/с")
            print(f"- Описание: {weather['description']}")
        else:
            print("Ошибка при получении погоды:", response.json())


class SearchClient:
    BASE_URL_PRODUCTS = "http://127.0.0.1:5000/search_products"
    BASE_URL_FOOD = "http://127.0.0.1:5000/search_food"
    BASE_URL_WEB = "http://127.0.0.1:5000/search_web"

    def search_products(self):
        query = input("Введите название товара для поиска: ")
        if not query:
            print("Название товара не может быть пустым.")
            return
        response = requests.get(self.BASE_URL_PRODUCTS, params={"query": query})
        if response.status_code == 200:
            data = response.json()
            print(f"Результаты поиска для '{query}':")
            print(f"1. Ozon: {data['ozon_link']}")
            print(f"2. Wildberries: {data['wildberries_link']}")
        else:
            print("Ошибка при поиске товаров:", response.json())

    def search_food(self):
        query = input("Введите название продукта для поиска: ")
        if not query:
            print("Название продукта не может быть пустым.")
            return
        response = requests.get(self.BASE_URL_FOOD, params={"query": query})
        if response.status_code == 200:
            data = response.json()
            print(f"Результаты поиска для '{query}':")
            print(f"1. Яндекс Маркет: {data['yandex_market_link']}")
            print(f"2. Сбермаркет: {data['sbermarket_link']}")
        else:
            print("Ошибка при поиске продуктов:", response.json())

    def search_web(self):
        query = input("Введите запрос для поиска в интернете: ")
        if not query:
            print("Запрос не может быть пустым.")
            return
        response = requests.get(self.BASE_URL_WEB, params={"query": query})
        if response.status_code == 200:
            data = response.json()
            print(f"Результаты поиска для '{query}':")
            print(f"1. Google: {data['google_link']}")
            print(f"2. Яндекс: {data['yandex_link']}")
        else:
            print("Ошибка при поиске в интернете:", response.json())


class GeolocationClient:
    def get_geolocation(self):
        try:
            response = requests.get("http://ip-api.com/json")
            data = response.json()
            if data['status'] == 'success':
                return data['lat'], data['lon']
            return None, None
        except Exception as e:
            print("Ошибка при получении геопозиции:", e)
            return None, None


class MapProviderClient:
    def choose_map_provider(self):
        print("\nВыберите карту:")
        print("1. Google Maps")
        print("2. Яндекс.Карты")
        choice = input("Введите номер: ")
        return "google" if choice == "1" else "yandex"


class PlacesClient:
    BASE_URL_RESTAURANTS = "http://127.0.0.1:5000/find_restaurants"
    BASE_URL_HOTELS = "http://127.0.0.1:5000/find_hotels"
    BASE_URL_ADDRESS = "http://127.0.0.1:5000/get_address"
    BASE_URL_PLACES = "http://127.0.0.1:5000/find_places"
    BASE_URL_EXACT = "http://127.0.0.1:5000/search_exact"

    def __init__(self):
        self.geolocation_client = GeolocationClient()
        self.map_provider_client = MapProviderClient()

    def find_restaurants(self):
        lat, lon = self._get_coordinates()
        if not lat or not lon:
            print("Не удалось определить вашу геопозицию.")
            return
        map_provider = self.map_provider_client.choose_map_provider()
        response = requests.get(self.BASE_URL_RESTAURANTS, params={"lat": lat, "lon": lon, "map_provider": map_provider})
        self._handle_response(response, "рестораны")

    def find_hotels(self):
        lat, lon = self._get_coordinates()
        if not lat or not lon:
            print("Не удалось определить вашу геопозицию.")
            return
        map_provider = self.map_provider_client.choose_map_provider()
        response = requests.get(self.BASE_URL_HOTELS, params={"lat": lat, "lon": lon, "map_provider": map_provider})
        self._handle_response(response, "отели")

    def get_client_address(self):
        lat, lon = self._get_coordinates()
        if not lat or not lon:
            print("Не удалось определить вашу геопозицию.")
            return
        map_provider = self.map_provider_client.choose_map_provider()
        response = requests.get(self.BASE_URL_ADDRESS, params={"lat": lat, "lon": lon, "map_provider": map_provider})
        if response.status_code == 200:
            address_data = response.json()
            address = address_data.get("address", "Address not available")
            map_link = address_data.get("map_link", "Map link not available")
            print(f"Ваш текущий адрес:\n{address}")
            print(f"Ссылка на карты: {map_link}")
        else:
            print("Ошибка при получении адреса:", response.json())

    def find_places(self):
        lat, lon = self._get_coordinates()
        if not lat or not lon:
            print("Не удалось определить вашу геопозицию.")
            return
        query = input("\nВведите запрос для поиска (например, 'аптека', 'магазин', 'театр'): ")
        if not query:
            print("Запрос не может быть пустым.")
            return
        map_provider = self.map_provider_client.choose_map_provider()
        response = requests.get(self.BASE_URL_PLACES, params={"lat": lat, "lon": lon, "query": query, "map_provider": map_provider})
        self._handle_response(response, "места")

    def search_exact(self):
        query = input("\nВведите адрес или название заведения для поиска: ")
        if not query:
            print("Запрос не может быть пустым.")
            return
        map_provider = self.map_provider_client.choose_map_provider()
        response = requests.get(self.BASE_URL_EXACT, params={"query": query, "map_provider": map_provider})
        if response.status_code == 200:
            place = response.json()
            print(f"\nРезультат поиска:")
            print(f"- Название: {place['name']}")
            print(f"- Адрес: {place['address']}")
            print(f"- Ссылка на карты: {place['map_link']}")
        else:
            print("Ошибка при поиске места:", response.json())

    def _get_coordinates(self):
        return self.geolocation_client.get_geolocation()

    def _handle_response(self, response, entity_name):
        if response.status_code == 200:
            data = response.json()
            if not data:
                print(f"{entity_name.capitalize()} не найдены.")
            else:
                print(f"\nБлижайшие {entity_name}:")
                for i, item in enumerate(data, start=1):
                    print(f"{i}. Название: {item['name']}")
                    print(f"   Адрес: {item['address']}")
                    print(f"   Рейтинг: {item.get('rating', 'N/A')}")
                    print(f"   Ссылка на карты: {item['map_link']}\n")
        else:
            print(f"Ошибка при поиске {entity_name}:", response.json())


class ClientApp:
    def __init__(self):
        self.weather_client = WeatherClient()
        self.search_client = SearchClient()
        self.places_client = PlacesClient()

    def run(self):
        while True:
            print("\nВыберите действие:")
            print("1. Получить погоду")
            print("2. Поиск товаров (Ozon, Wildberries)")
            print("3. Поиск продовольственных товаров (Яндекс Маркет, Сбермаркет)")
            print("4. Найти рестораны")
            print("5. Найти отели")
            print("6. Узнать свой адрес")
            print("7. Поиск в интернете (Google, Яндекс)")
            print("8. Поиск мест рядом")
            print("9. Точный поиск места (по адресу или названию)")
            print("10. Выход")
            choice = input("Введите номер действия: ")
            if choice == "1":
                mode = input("Получить погоду по (1)городу или (2)автоматически? ")
                if mode == "1":
                    city = input("Введите название города: ")
                    self.weather_client.get_weather(city=city)
                elif mode == "2":
                    self.weather_client.get_weather()
                else:
                    print("Неверный выбор.")
            elif choice == "2":
                self.search_client.search_products()
            elif choice == "3":
                self.search_client.search_food()
            elif choice == "4":
                self.places_client.find_restaurants()
            elif choice == "5":
                self.places_client.find_hotels()
            elif choice == "6":
                self.places_client.get_client_address()
            elif choice == "7":
                self.search_client.search_web()
            elif choice == "8":
                self.places_client.find_places()
            elif choice == "9":
                self.places_client.search_exact()
            elif choice == "10":
                print("До свидания!")
                break
            else:
                print("Неверный выбор. Попробуйте снова.")


if __name__ == "__main__":
    app = ClientApp()
    app.run()
