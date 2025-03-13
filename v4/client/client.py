import sys
import requests
import hmac
import hashlib
import socket
import threading
import platform
import psutil
import uuid
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QPushButton,
    QMessageBox, QDialog, QVBoxLayout, QLineEdit, QTextEdit, QTextBrowser
)
from PyQt5.QtGui import QDesktopServices

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('client.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


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


class EncryptedClient:
    def __init__(self):
        self.cipher = VigenereCipher("негр")

    def encrypt_request(self, params):
        try:
            return {k: self.cipher.encrypt(str(v)) for k, v in params.items()}
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            return params

    def decrypt_response(self, data):
        try:
            if isinstance(data, dict):
                return {k: self.cipher.decrypt(v) for k, v in data.items()}
            return data
        except Exception as e:
            logger.error(f"Ошибка дешифровки: {e}")
            return data

    def generate_hmac(self, data):
        return hmac.new("негр".encode(), str(data).encode(), hashlib.sha256).hexdigest()


class DeviceInfo:
    @staticmethod
    def get_device_info():
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            system_info = platform.uname()
            return {
                "hostname": hostname,
                "ip_address": ip_address,
                "system": system_info.system,
                "node_name": system_info.node,
                "release": system_info.release,
                "version": system_info.version,
                "machine": system_info.machine,
                "processor": system_info.processor,
                "cpu_count": psutil.cpu_count(logical=True),
                "memory_total": psutil.virtual_memory().total,
                "disk_usage": psutil.disk_usage('/').percent,
                "boot_time": psutil.boot_time(),
                "mac_address": ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
            }
        except Exception as e:
            print(f"Ошибка получения информации об устройстве: {e}")
            return {}


class BaseClient:
    BASE_URL = "http://127.0.0.1:5000"

    def __init__(self):
        self.encryption_handler = EncryptedClient()

    def _get(self, endpoint, params=None):
        try:
            if params is None:
                params = {}

            logger.debug(f"Исходные параметры: {params}")

            device_info = DeviceInfo.get_device_info()
            combined_params = {**params, **device_info}
            encrypted_params = self.encryption_handler.encrypt_request(combined_params)
            logger.debug(f"Зашифрованные параметры: {encrypted_params}")

            hmac_signature = self.encryption_handler.generate_hmac(encrypted_params)
            headers = {"X-HMAC-Signature": hmac_signature}

            response = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                params=encrypted_params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            encrypted_data = response.json()
            decrypted_data = self.encryption_handler.decrypt_response(encrypted_data)
            logger.debug(f"Расшифрованный ответ: {decrypted_data}")

            return decrypted_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса: {str(e)}")
            return {"error": f"Ошибка сети: {str(e)}"}
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {str(e)}", exc_info=True)
            return {"error": "Внутренняя ошибка клиента"}


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
        return data

    def format_weather(self, data):
        if "error" in data:
            return data["error"]
        formatted = [f"Погода в {data['city']}, {data['country']}:"]
        for key, label in self.WEATHER_LABELS.items():
            formatted.append(f"{label}: {data[key]}{self._get_unit(key)}")
        return "\n".join(formatted)

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
            'results': {
                'ozon_link': 'Ozon',
                'wildberries_link': 'Wildberries'
            }
        },
        'food': {
            'endpoint': 'search_food',
            'results': {
                'yandex_market_link': 'Яндекс Маркет',
                'sbermarket_link': 'Сбермаркет'
            }
        },
        'web': {
            'endpoint': 'search_web',
            'results': {
                'google_link': 'Google',
                'yandex_link': 'Яндекс'
            }
        }
    }

    def search(self, search_type, query):
        config = self.SERVICES[search_type]
        data = self._get(config['endpoint'], {"query": query})
        return data


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
            logger.error(f"Ошибка определения геопозиции: {e}")
            return None, None


class MapProviderClient:
    PROVIDERS = {
        '1': ('google', 'Google Maps'),
        '2': ('yandex', 'Яндекс.Карты')
    }


class PlacesClient(BaseClient):
    ENDPOINTS = {
        'restaurants': 'find_restaurants',
        'hotels': 'find_hotels',
        'address': 'get_address',
        'places': 'find_places',
        'exact': 'search_exact'
    }

    def __init__(self):
        super().__init__()
        self.geolocation = GeolocationClient()
        self.map_provider = MapProviderClient()

    def handle_action(self, action_type, query=None):
        try:
            coords = self._get_coordinates()
            if not coords:
                return {"error": "Не удалось определить местоположение"}

            logger.debug(f"Получены координаты: {coords}")

            encrypted_coords = self.encryption_handler.encrypt_request({
                'lat': str(coords[0]),
                'lon': str(coords[1])
            })

            params = {
                'lat': encrypted_coords['lat'],
                'lon': encrypted_coords['lon'],
                'map_provider': 'google'
            }
            if query:
                params['query'] = query

            logger.debug(f"Параметры запроса: {params}")
            return self._get(self.ENDPOINTS[action_type], params)

        except Exception as e:
            logger.error(f"Ошибка в handle_action: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _get_coordinates(self):
        return self.geolocation.get_coordinates()


STYLESHEET = """
QMainWindow {
    background-color: #1a1a1a;
}

QPushButton {
    background-color: #2d2d2d;
    color: #00ff9d;
    border: 2px solid #00ff9d;
    border-radius: 10px;
    padding: 15px;
    font-size: 14px;
    min-width: 150px;
}

QPushButton:hover {
    background-color: #3d3d3d;
}

QPushButton:pressed {
    background-color: #4d4d4d;
}

QLineEdit {
    background-color: #2d2d2d;
    color: #00ff9d;
    border: 2px solid #00ff9d;
    border-radius: 5px;
    padding: 5px;
    font-size: 14px;
}

QLabel {
    color: #00ff9d;
    font-size: 14px;
}

QTextEdit {
    background-color: #2d2d2d;
    color: #00ff9d;
    border: 2px solid #00ff9d;
    border-radius: 5px;
    padding: 5px;
    font-size: 14px;
}

QMessageBox {
    background-color: #1a1a1a;
}

QDialog {
    background-color: #1a1a1a;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Future Client")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet(STYLESHEET)

        self.weather_client = WeatherClient()
        self.search_client = SearchClient()
        self.places_client = PlacesClient()

        self.device_info = {}
        self.init_ui()
        self.start_device_info_thread()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QGridLayout()
        central_widget.setLayout(layout)

        buttons = [
            ("Погода", self.show_weather_dialog),
            ("Поиск товаров", lambda: self.show_search_dialog('products')),
            ("Поиск продуктов", lambda: self.show_search_dialog('food')),
            ("Рестораны", lambda: self.handle_places('restaurants')),
            ("Отели", lambda: self.handle_places('hotels')),
            ("Текущий адрес", self.handle_address),
            ("Веб-поиск", lambda: self.show_search_dialog('web')),
            ("Поиск мест", lambda: self.show_places_search_dialog()),
            ("Точный поиск", self.show_exact_search_dialog),
            ("Выход", self.close)
        ]

        positions = [(i // 3, i % 3) for i in range(9)] + [(3, 1)]
        for (text, handler), pos in zip(buttons, positions):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            layout.addWidget(btn, *pos)

    def start_device_info_thread(self):
        def get_device_info():
            self.device_info = DeviceInfo.get_device_info()
            logger.debug(f"Информация об устройстве: {self.device_info}")

        thread = threading.Thread(target=get_device_info)
        thread.daemon = True
        thread.start()

    def show_error(self, message):
        QMessageBox.critical(self, "Ошибка", message)

    def show_weather_dialog(self):
        dialog = WeatherDialog(self)
        dialog.exec_()

    def show_search_dialog(self, search_type):
        dialog = SearchDialog(search_type, self)
        dialog.exec_()

    def handle_places(self, action_type):
        data = self.places_client.handle_action(action_type)
        self.show_places_result(data, action_type)

    def show_places_result(self, data, entity_name):
        if "error" in data:
            self.show_error(data["error"])
            return

        dialog = ResultDialog(f"Результаты поиска ({entity_name})", data, self)
        dialog.exec_()

    def handle_address(self):
        data = self.places_client.handle_action('address')
        self.show_address_result(data)

    def show_address_result(self, data):
        if "error" in data:
            self.show_error(data["error"])
            return

        dialog = ResultDialog("Текущий адрес", data, self)
        dialog.exec_()

    def show_places_search_dialog(self):
        dialog = PlacesSearchDialog(self)
        dialog.exec_()

    def show_exact_search_dialog(self):
        dialog = ExactSearchDialog(self)
        dialog.exec_()


class WeatherDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Погода")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.mode_btn = QPushButton("Автоматическое определение")
        self.mode_btn.clicked.connect(self.toggle_mode)
        layout.addWidget(self.mode_btn)

        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Введите город")
        self.city_input.hide()
        layout.addWidget(self.city_input)

        self.search_btn = QPushButton("Получить погоду")
        self.search_btn.clicked.connect(self.get_weather)
        layout.addWidget(self.search_btn)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        self.mode = 'auto'

    def toggle_mode(self):
        self.mode = 'manual' if self.mode == 'auto' else 'auto'
        self.mode_btn.setText("Ввести город вручную" if self.mode == 'auto' else "Автоматическое определение")
        self.city_input.setVisible(self.mode == 'manual')

    def get_weather(self):
        city = self.city_input.text() if self.mode == 'manual' else None
        data = self.parent.weather_client.get_weather(city)

        if "error" in data:
            self.parent.show_error(data["error"])
            return

        self.result_area.setText(self.parent.weather_client.format_weather(data))


class SearchDialog(QDialog):
    def __init__(self, search_type, parent):
        super().__init__(parent)
        self.parent = parent
        self.search_type = search_type
        self.setWindowTitle(
            ["Поиск товаров", "Поиск продуктов", "Веб-поиск"][["products", "food", "web"].index(search_type)])
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Введите запрос")
        layout.addWidget(self.input_field)

        self.search_btn = QPushButton("Поиск")
        self.search_btn.clicked.connect(self.do_search)
        layout.addWidget(self.search_btn)

        self.result_area = QTextBrowser()
        self.result_area.setOpenExternalLinks(True)
        self.result_area.anchorClicked.connect(self.open_link)
        layout.addWidget(self.result_area)

    def do_search(self):
        query = self.input_field.text()
        if not query:
            self.parent.show_error("Запрос не может быть пустым")
            return

        data = self.parent.search_client.search(self.search_type, query)
        if "error" in data:
            self.parent.show_error(data["error"])
            return

        result_text = []
        for key, label in self.parent.search_client.SERVICES[self.search_type]['results'].items():
            url = data.get(key)
            if url:
                result_text.append(
                    f'<p style="color:#00ff9d;">{label}: '
                    f'<a href="{url}" style="color:#00ff9d;text-decoration:underline;">{url}</a></p>'
                )
            else:
                result_text.append(f'<p style="color:#ff0000;">{label}: Ссылка недоступна</p>')

        self.result_area.setHtml('\n'.join(result_text))

    def open_link(self, url):
        QDesktopServices.openUrl(url)


class ResultDialog(QDialog):
    def __init__(self, title, data, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.anchorClicked.connect(self.open_link)
        text.setHtml(self._format_data())
        layout.addWidget(text)

    def open_link(self, url):
        QDesktopServices.openUrl(url)

    def _format_data(self):
        if isinstance(self.data, list):
            return self._format_list_data()
        elif isinstance(self.data, dict):
            return self._format_dict_data()
        else:
            return f"<pre>{self.data}</pre>"

    def _format_list_data(self):
        items_html = []
        for item in self.data:
            items_html.append(f"""
                <div style="margin-bottom: 20px; border-bottom: 1px solid #00ff9d; padding-bottom: 10px;">
                    <h3 style="margin: 0; color: #00ff9d;">{item.get('name', 'Название не указано')}</h3>
                    <p style="margin: 5px 0; color: #00ff9d;">📍 {item.get('address', 'Адрес не указан')}</p>
                    <p style="margin: 5px 0; color: {self._get_rating_color(item)};">★ Рейтинг: {item.get('rating', 'Н/Д')}</p>
                    <p style="margin: 5px 0; color: #00ff9d;">🌐 <a href="{item.get('map_link', '')}" style="color: #00ff9d; text-decoration: none;">{item.get('map_link', 'Ссылка отсутствует')}</a></p>
                </div>
            """)
        return f"""
            <html>
            <body style="color: #00ff9d; font-family: Arial; font-size: 12pt;">
                {'<hr>'.join(items_html)}
            </body>
            </html>
        """

    def _format_dict_data(self):
        if "address" in self.data:
            return f"""
                <html>
                <body style="color: #00ff9d; font-family: Arial; font-size: 12pt;">
                    <div style="margin-bottom: 20px;">
                        <h3 style="margin: 0;">Текущий адрес</h3>
                        <p>📍 {self.data['address']}</p>
                        <p>🌐 <a href="{self.data.get('map_link', '')}" style="color: #00ff9d; text-decoration: none;">{self.data.get('map_link', 'Ссылка отсутствует')}</a></p>
                    </div>
                </body>
                </html>
            """
        return f"<pre>{self.data}</pre>"

    def _get_rating_color(self, item):
        rating = item.get('rating', 'Н/Д')
        return "#00ff00" if str(rating).isdigit() else "#888888"


class PlacesSearchDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Поиск мест")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Введите запрос (например, 'аптека', 'магазин')")
        layout.addWidget(self.input_field)

        self.search_btn = QPushButton("Поиск")
        self.search_btn.clicked.connect(self.do_search)
        layout.addWidget(self.search_btn)

    def do_search(self):
        query = self.input_field.text()
        if not query:
            self.parent.show_error("Запрос не может быть пустым")
            return

        data = self.parent.places_client.handle_action('places', query)
        self.parent.show_places_result(data, 'places')


class ExactSearchDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Точный поиск")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Введите адрес или название заведения")
        layout.addWidget(self.input_field)

        self.search_btn = QPushButton("Поиск")
        self.search_btn.clicked.connect(self.do_search)
        layout.addWidget(self.search_btn)

    def do_search(self):
        query = self.input_field.text()
        if not query:
            self.parent.show_error("Запрос не может быть пустым")
            return

        data = self.parent.places_client.handle_action('exact', query)
        self.parent.show_places_result(data, 'exact')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
