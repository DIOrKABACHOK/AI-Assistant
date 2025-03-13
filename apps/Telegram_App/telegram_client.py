import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
import requests
import hmac
import hashlib
import socket
import platform
import psutil
import uuid

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:5000"
HMAC_KEY = "негр"
SECRET_KEY = "негр"

INPUT_QUERY, GET_LOCATION = range(2)


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
        self.cipher = VigenereCipher(SECRET_KEY)

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
        return hmac.new(HMAC_KEY.encode(), str(data).encode(), hashlib.sha256).hexdigest()


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
                "mac_address": ':'.join(
                    ['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации об устройстве: {e}")
            return {}


class BaseClient:
    def __init__(self):
        self.encryption_handler = EncryptedClient()
        self.device_info = DeviceInfo.get_device_info()

    def _prepare_params(self, params):
        combined = {**params, **self.device_info}
        encrypted = self.encryption_handler.encrypt_request(combined)
        return {
            "params": encrypted,
            "headers": {"X-HMAC-Signature": self.encryption_handler.generate_hmac(encrypted)}
        }

    def _process_response(self, response):
        try:
            response.raise_for_status()
            encrypted_data = response.json()
            return self.encryption_handler.decrypt_response(encrypted_data)
        except Exception as e:
            logger.error(f"Ошибка обработки ответа: {str(e)}")
            return {"error": "Ошибка обработки данных"}


class TelegramBot(BaseClient):
    def __init__(self, token: str):
        super().__init__()
        self.application = Application.builder().token(token).build()
        self._register_handlers()

    def _main_keyboard(self):
        return ReplyKeyboardMarkup([
            ["🌤 Погода", "🛍 Товары"],
            ["🍔 Еда", "🍴 Рестораны"],
            ["🏨 Отели", "📍 Адрес"],
            ["🌐 Веб-поиск", "🔍 Места"],
            ["🎯 Точный поиск"]
        ], resize_keyboard=True)

    def _cancel_keyboard(self):
        return ReplyKeyboardMarkup([["🚫 Отмена"]], resize_keyboard=True)

    def _register_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_main_menu)],
            states={
                INPUT_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_input)],
                GET_LOCATION: [
                    MessageHandler(filters.LOCATION, self._handle_location),
                    MessageHandler(filters.TEXT, self._handle_location_text)
                ]
            },
            fallbacks=[CommandHandler("cancel", self._cancel)],
        )

        self.application.add_handler(conv_handler)
        self.application.add_error_handler(self._error_handler)

    async def _handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        context.user_data.clear()

        if text == "🌤 Погода":
            await update.message.reply_text(
                "Отправьте местоположение или введите город:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📍 Отправить местоположение", request_location=True)],
                    ["🚫 Отмена"]
                ], resize_keyboard=True)
            )
            return GET_LOCATION

        elif text == "🛍 Товары":
            await update.message.reply_text("Введите название товара:", reply_markup=self._cancel_keyboard())
            context.user_data["action"] = "products"
            return INPUT_QUERY

        elif text == "🍔 Еда":
            await update.message.reply_text("Что ищем из еды?", reply_markup=self._cancel_keyboard())
            context.user_data["action"] = "food"
            return INPUT_QUERY

        elif text == "🍴 Рестораны":
            await update.message.reply_text(
                "Отправьте ваше местоположение для поиска ресторанов:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📍 Отправить местоположение", request_location=True)],
                    ["🚫 Отмена"]
                ], resize_keyboard=True)
            )
            context.user_data["action"] = "restaurants"
            return GET_LOCATION

        elif text == "🏨 Отели":
            await update.message.reply_text(
                "Отправьте ваше местоположение для поиска отелей:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📍 Отправить местоположение", request_location=True)],
                    ["🚫 Отмена"]
                ], resize_keyboard=True)
            )
            context.user_data["action"] = "hotels"
            return GET_LOCATION

        elif text == "📍 Адрес":
            await update.message.reply_text(
                "Отправьте ваше местоположение:",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("📍 Отправить местоположение", request_location=True)],
                    ["🚫 Отмена"]
                ], resize_keyboard=True)
            )
            context.user_data["action"] = "address"
            return GET_LOCATION

        elif text == "🌐 Веб-поиск":
            await update.message.reply_text("Введите поисковый запрос:", reply_markup=self._cancel_keyboard())
            context.user_data["action"] = "web"
            return INPUT_QUERY

        elif text == "🔍 Места":
            await update.message.reply_text(
                "Что ищем? (например: аптека, банкомат)",
                reply_markup=self._cancel_keyboard()
            )
            context.user_data["action"] = "places"
            return INPUT_QUERY

        elif text == "🎯 Точный поиск":
            await update.message.reply_text("Введите точное название места:", reply_markup=self._cancel_keyboard())
            context.user_data["action"] = "exact"
            return INPUT_QUERY

        await update.message.reply_text("Используйте кнопки меню:", reply_markup=self._main_keyboard())
        return ConversationHandler.END

    async def _handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text

        if text == "🚫 Отмена":
            return await self._cancel(update, context)

        action = context.user_data.get("action")
        query = text

        response = None  # Инициализация переменной
        try:
            base_params = {
                "user_id": update.message.from_user.id,
                "username": update.message.from_user.username,
                "first_name": update.message.from_user.first_name,
                "last_name": update.message.from_user.last_name,
            }

            if action == "products":
                prepared = self._prepare_params({**base_params, "query": query})
                response = requests.get(f"{BASE_URL}/search_products", **prepared)
                data = self._process_response(response)
                message = f"Результаты поиска товаров:\n\n🔗 Ozon: {data['ozon_link']}\n🔗 Wildberries: {data['wildberries_link']}"

            elif action == "food":
                prepared = self._prepare_params({**base_params, "query": query})
                response = requests.get(f"{BASE_URL}/search_food", **prepared)
                data = self._process_response(response)
                message = f"Результаты поиска еды:\n\n🔗 Яндекс.Маркет: {data['yandex_market_link']}\n🔗 СберМаркет: {data['sbermarket_link']}"

            elif action == "web":
                prepared = self._prepare_params({**base_params, "query": query})
                response = requests.get(f"{BASE_URL}/search_web", **prepared)
                data = self._process_response(response)
                message = f"Результаты поиска:\n\n🔍 Google: {data['google_link']}\n🔍 Яндекс: {data['yandex_link']}"

            elif action == "places":
                context.user_data["query"] = query
                await update.message.reply_text(
                    "Отправьте ваше местоположение:",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("📍 Отправить местоположение", request_location=True)],
                        ["🚫 Отмена"]
                    ], resize_keyboard=True)
                )
                return GET_LOCATION

            elif action == "exact":
                prepared = self._prepare_params({**base_params, "query": query})
                response = requests.get(f"{BASE_URL}/search_exact", **prepared)
                data = self._process_response(response)
                if "error" in data:
                    message = "❌ " + data["error"]
                else:
                    message = (
                        f"📍 {data['name']}\n"
                        f"Адрес: {data['address']}\n"
                        f"Рейтинг: {data.get('rating', 'Н/Д')}\n"
                        f"Ссылка на карту: {data['map_link']}"
                    )

            if response is not None and response.status_code != 200:
                message = "⚠️ Ошибка при выполнении запроса"

        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            message = "⚠️ Произошла внутренняя ошибка"

        await update.message.reply_text(message, disable_web_page_preview=True)
        return await self._return_to_main(update)

    async def _handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        location = update.message.location
        lat = location.latitude
        lon = location.longitude
        action = context.user_data.get("action")

        try:
            base_params = {
                "user_id": update.message.from_user.id,
                "username": update.message.from_user.username,
                "first_name": update.message.from_user.first_name,
                "last_name": update.message.from_user.last_name,
                "lat": str(lat),
                "lon": str(lon)
            }

            if action == "weather":
                prepared = self._prepare_params(base_params)
                response = requests.get(f"{BASE_URL}/get_weather", **prepared)
                data = self._process_response(response)
                message = (
                    f"🌤 Погода в {data['city']}:\n"
                    f"🌡 Температура: {data['temperature']}°C\n"
                    f"💨 Ощущается как: {data['feels_like']}°C\n"
                    f"💧 Влажность: {data['humidity']}%\n"
                    f"🌀 Давление: {data['pressure']} hPa\n"
                    f"🌪 Ветер: {data['wind_speed']} м/с\n"
                    f"📝 Описание: {data['description']}"
                )

            elif action == "restaurants":
                prepared = self._prepare_params(base_params)
                response = requests.get(f"{BASE_URL}/find_restaurants", **prepared)
                data = self._process_response(response)
                message = self._format_places(data, "Рестораны")

            elif action == "hotels":
                prepared = self._prepare_params(base_params)
                response = requests.get(f"{BASE_URL}/find_hotels", **prepared)
                data = self._process_response(response)
                message = self._format_places(data, "Отели")

            elif action == "address":
                prepared = self._prepare_params(base_params)
                response = requests.get(f"{BASE_URL}/get_address", **prepared)
                data = self._process_response(response)
                message = f"📍 Текущий адрес:\n{data.get('address', 'Не определен')}\nСсылка на карту: {data.get('map_link', '')}"

            elif action == "places":
                query = context.user_data.get("query")
                prepared = self._prepare_params({**base_params, "query": query})
                response = requests.get(f"{BASE_URL}/find_places", **prepared)
                data = self._process_response(response)
                message = self._format_places(data, "Результаты поиска")

            if response.status_code != 200:
                message = "⚠️ Ошибка при выполнении запроса"

        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            message = "⚠️ Произошла внутренняя ошибка"

        await update.message.reply_text(message, disable_web_page_preview=True)
        return await self._return_to_main(update)

    async def _handle_location_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text

        if text == "🚫 Отмена":
            return await self._cancel(update, context)

        city = text
        prepared = self._prepare_params({"q": city})
        response = requests.get(f"{BASE_URL}/get_weather", **prepared)
        data = self._process_response(response)

        if "error" in data:
            message = "❌ " + data["error"]
        else:
            message = (
                f"🌤 Погода в {data['city']}:\n"
                f"🌡 Температура: {data['temperature']}°C\n"
                f"💨 Ощущается как: {data['feels_like']}°C\n"
                f"💧 Влажность: {data['humidity']}%\n"
                f"🌀 Давление: {data['pressure']} hPa\n"
                f"🌪 Ветер: {data['wind_speed']} м/с\n"
                f"📝 Описание: {data['description']}"
            )

        await update.message.reply_text(message)
        return await self._return_to_main(update)

    def _format_places(self, places, title):
        if not places:
            return "❌ Ничего не найдено"

        message = [f"🏷 {title}:"]
        for place in places[:5]:
            message.append(
                f"\n📍 {place.get('name', 'Без названия')}\n"
                f"Адрес: {place.get('address', 'Не указан')}\n"
                f"Рейтинг: {place.get('rating', 'Н/Д')}\n"
                f"Ссылка: {place.get('map_link', 'Нет ссылки')}\n"
            )
        return "\n".join(message)

    async def _return_to_main(self, update: Update):
        await update.message.reply_text("Выберите действие:", reply_markup=self._main_keyboard())
        return ConversationHandler.END

    async def _cancel(self, update: Update):
        await update.message.reply_text("Действие отменено", reply_markup=self._main_keyboard())
        return ConversationHandler.END

    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Ошибка: %s", context.error, exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.", reply_markup=self._main_keyboard())

    def run(self):
        self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot("7828093872:AAGp7KAHGfnINWO2H27NXX8fvlh4XxZrWAU")
    bot.run()
