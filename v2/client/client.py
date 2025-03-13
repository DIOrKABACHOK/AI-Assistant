import requests


class BaseClient:
    BASE_URL = "http://127.0.0.1:5000"

    def _get(self, endpoint, params=None):
        response = requests.get(f"{self.BASE_URL}/{endpoint}", params=params)
        return response.json() if response.ok else {"error": response.text}


class WeatherClient(BaseClient):
    WEATHER_LABELS = {
        'temperature': 'Температура',
        'feels_like': 'Ощущается как',
        'humidity': 'Влажность',
        'pressure': 'Давление',
        'wind_speed': 'Скорость ветра',
        'description': 'Описание'
    }

    def get_weather(self, city=None):
        data = self._get("get_weather", {"city": city} if city else {})
        self._print_weather(data) if "error" not in data else self._print_error(data["error"])

    def _print_weather(self, data):
        print(f"\nПогода в {data['city']}, {data['country']}:")
        for key, label in self.WEATHER_LABELS.items():
            print(f"- {label}: {data[key]}{self._get_unit(key)}")

    @staticmethod
    def _get_unit(key):
        units = {
            'temperature': '°C',
            'feels_like': '°C',
            'humidity': '%',
            'pressure': ' hPa',
            'wind_speed': ' м/с'
        }
        return units.get(key, '')


class SearchClient(BaseClient):
    SERVICES = {
        'products': {
            'endpoint': 'search_products',
            'prompt': 'Введите название товара для поиска: ',
            'results': {
                'ozon_link': 'Ozon',
                'wildberries_link': 'Wildberries'
            }
        },
        'food': {
            'endpoint': 'search_food',
            'prompt': 'Введите название продукта для поиска: ',
            'results': {
                'yandex_market_link': 'Яндекс Маркет',
                'sbermarket_link': 'Сбермаркет'
            }
        },
        'web': {
            'endpoint': 'search_web',
            'prompt': 'Введите поисковый запрос: ',
            'results': {
                'google_link': 'Google',
                'yandex_link': 'Яндекс'
            }
        }
    }

    def search(self, search_type):
        config = self.SERVICES[search_type]
        query = self._get_input(config['prompt'])
        if not query:
            return

        data = self._get(config['endpoint'], {"query": query})
        self._print_results(query, data, config['results']) if "error" not in data else self._print_error(data["error"])

    @staticmethod
    def _get_input(prompt):
        query = input(prompt).strip()
        if not query:
            print("Запрос не может быть пустым.")
        return query

    def _print_results(self, query, data, services):
        print(f"\nРезультаты поиска для '{query}':")
        for i, (key, name) in enumerate(services.items(), 1):
            print(f"{i}. {name}: {data[key]}")


class GeolocationClient:
    @staticmethod
    def get_coordinates():
        try:
            response = requests.get("http://ip-api.com/json")
            if response.ok:
                data = response.json()
                return (data['lat'], data['lon']) if data['status'] == 'success' else (None, None)
            return None, None
        except Exception as e:
            print(f"Ошибка определения геопозиции: {e}")
            return None, None


class MapProviderClient:
    PROVIDERS = {
        '1': ('google', 'Google Maps'),
        '2': ('yandex', 'Яндекс.Карты')
    }

    @staticmethod
    def choose_provider():
        print("\nВыберите карту:")
        for key, (_, name) in MapProviderClient.PROVIDERS.items():
            print(f"{key}. {name}")

        choice = input("Введите номер: ").strip()
        return MapProviderClient.PROVIDERS.get(choice, ('google', 'Google Maps'))[0]


class PlacesClient(BaseClient):
    ENDPOINTS = {
        'restaurants': 'find_restaurants',
        'hotels': 'find_hotels',
        'address': 'get_address',
        'places': 'find_places',
        'exact': 'search_exact'
    }

    def __init__(self):
        self.geolocation = GeolocationClient()
        self.map_provider = MapProviderClient()

    def handle_action(self, action_type, params=None, needs_query=False):
        coords = self._get_coordinates()
        if not coords:
            print("Не удалось определить ваше местоположение.")
            return

        query = input(params['prompt']).strip() if needs_query else None
        if needs_query and not query:
            print(params['empty_message'])
            return

        response_params = {
            'lat': coords[0],
            'lon': coords[1],
            'map_provider': self.map_provider.choose_provider()
        }
        if needs_query:
            response_params['query'] = query

        data = self._get(self.ENDPOINTS[action_type], response_params)
        self._print_response(data, params['entity_name']) if "error" not in data else self._print_error(data["error"])

    def search_exact(self):
        query = input("\nВведите адрес или название заведения: ").strip()
        if not query:
            print("Запрос не может быть пустым.")
            return

        data = self._get(self.ENDPOINTS['exact'], {
            'query': query,
            'map_provider': self.map_provider.choose_provider()
        })
        self._print_exact_result(data) if "error" not in data else self._print_error(data["error"])

    def _get_coordinates(self):
        return self.geolocation.get_coordinates()

    def _print_response(self, data, entity_name):
        if not data:
            print(f"\n{entity_name.capitalize()} не найдены.")
            return

        print(f"\nНайдены {entity_name}:")
        for i, item in enumerate(data, 1):
            print(f"{i}. {item['name']}")
            print(f"   Адрес: {item.get('address', 'Н/Д')}")
            print(f"   Рейтинг: {item.get('rating', 'Н/Д')}")
            print(f"   Ссылка: {item.get('map_link', 'Н/Д')}\n")

    def _print_exact_result(self, data):
        print("\nРезультат поиска:")
        print(f"- Название: {data.get('name', 'Неизвестно')}")
        print(f"- Адрес: {data.get('address', 'Н/Д')}")
        print(f"- Ссылка: {data.get('map_link', 'Н/Д')}")


class ClientApp:
    MENU_OPTIONS = {
        '1': ('Погода', 'weather'),
        '2': ('Поиск товаров', 'products'),
        '3': ('Поиск продуктов', 'food'),
        '4': ('Рестораны', 'restaurants'),
        '5': ('Отели', 'hotels'),
        '6': ('Текущий адрес', 'address'),
        '7': ('Веб-поиск', 'web'),
        '8': ('Поиск мест', 'places'),
        '9': ('Точный поиск', 'exact'),
        '10': ('Выход', 'exit')
    }

    ACTIONS_CONFIG = {
        'restaurants': {
            'prompt': '',
            'entity_name': 'рестораны',
            'empty_message': ''
        },
        'hotels': {
            'prompt': '',
            'entity_name': 'отели',
            'empty_message': ''
        },
        'places': {
            'prompt': "\nВведите запрос для поиска (например, 'аптека', 'магазин', 'театр'): ",
            'entity_name': 'места',
            'empty_message': 'Запрос не может быть пустым.'
        }
    }

    def __init__(self):
        self.weather_client = WeatherClient()
        self.search_client = SearchClient()
        self.places_client = PlacesClient()

    def run(self):
        while True:
            self._print_menu()
            choice = input("\nВведите номер действия: ").strip()

            if choice == '10':
                print("\nДо свидания!")
                break

            if choice not in self.MENU_OPTIONS:
                print("\nНеверный выбор. Попробуйте снова.")
                continue

            self._handle_choice(choice)

    def _print_menu(self):
        print("\n" + "=" * 20 + " МЕНЮ " + "=" * 20)
        for key, (name, _) in self.MENU_OPTIONS.items():
            print(f"{key}. {name}")

    def _handle_choice(self, choice):
        action_type = self.MENU_OPTIONS[choice][1]

        if action_type == 'weather':
            self._handle_weather()
        elif action_type in ('products', 'food', 'web'):
            self.search_client.search(action_type)
        elif action_type in ('restaurants', 'hotels', 'places'):
            self.places_client.handle_action(
                action_type,
                params=self.ACTIONS_CONFIG[action_type],
                needs_query=(action_type == 'places')
            )
        elif action_type == 'address':
            self._handle_address()
        elif action_type == 'exact':
            self.places_client.search_exact()

    def _handle_weather(self):
        mode = input("\nПолучить погоду по (1) городу или (2) автоматически? ").strip()
        if mode == '1':
            city = input("Введите название города: ").strip()
            self.weather_client.get_weather(city=city)
        elif mode == '2':
            self.weather_client.get_weather()
        else:
            print("Неверный выбор.")

    def _handle_address(self):
        data = self.places_client._get(self.places_client.ENDPOINTS['address'], {
            'lat': self.places_client.geolocation.get_coordinates()[0],
            'lon': self.places_client.geolocation.get_coordinates()[1],
            'map_provider': self.places_client.map_provider.choose_provider()
        })
        if "error" not in data:
            print(f"\nТекущий адрес: {data.get('address', 'Н/Д')}")
            print(f"Ссылка на карты: {data.get('map_link', 'Н/Д')}")
        else:
            print(f"Ошибка: {data['error']}")


if __name__ == "__main__":
    ClientApp().run()
