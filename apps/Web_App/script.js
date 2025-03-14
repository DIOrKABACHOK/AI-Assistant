const HMAC_KEY = "негр";
const SECRET_KEY = "негр";

let mode = 'auto';
let currentSearchType = '';

class VigenereCipher {
    constructor(key) {
        if (!key) throw new Error("Ключ не может быть пустым");
        this.key = key.toLowerCase().replace(' ', '');
        this.alphabet = 'абвгдежзийклмнопрстуфхцчшщъыьэюя0123456789.,- ';
        this.charToIndex = Object.fromEntries(
            [...this.alphabet].map((char, i) => [char, i])
        );
    }

    encrypt(text) {
        return [...text.toLowerCase()].map((char, i) => {
            if (this.alphabet.includes(char)) {
                const shift = this.charToIndex[this.key[i % this.key.length]];
                const newIndex = (this.charToIndex[char] + shift) % this.alphabet.length;
                return this.alphabet[newIndex];
            }
            return char;
        }).join('');
    }

    decrypt(text) {
        return [...text.toLowerCase()].map((char, i) => {
            if (this.alphabet.includes(char)) {
                const shift = this.charToIndex[this.key[i % this.key.length]];
                const newIndex = (this.charToIndex[char] - shift + this.alphabet.length) % this.alphabet.length;
                return this.alphabet[newIndex];
            }
            return char;
        }).join('');
    }
}

class EncryptedClient {
    constructor() {
        this.cipher = new VigenereCipher(SECRET_KEY);
    }

    encryptRequest(params) {
        try {
            return Object.fromEntries(
                Object.entries(params).map(([k, v]) => [k, this.cipher.encrypt(String(v))])
            );
        } catch (e) {
            console.error("Ошибка шифрования:", e);
            return params;
        }
    }

    decryptResponse(data) {
        try {
            if (typeof data === 'object') {
                return Object.fromEntries(
                    Object.entries(data).map(([k, v]) => [k, this.cipher.decrypt(v)])
                );
            }
            return data;
        } catch (e) {
            console.error("Ошибка дешифровки:", e);
            return data;
        }
    }
}

const encryptedClient = new EncryptedClient();

function generateHmac(data) {
    return CryptoJS.HmacSHA256(JSON.stringify(data), HMAC_KEY).toString(CryptoJS.enc.Hex);
}

function closeAllDialogs() {
    document.querySelectorAll('.dialog').forEach(dialog => dialog.classList.add('hidden'));
}

function showWeatherDialog() {
    closeAllDialogs();
    const dialog = document.getElementById('weather-dialog');
    dialog.classList.remove('hidden');

    mode = 'auto';
    document.getElementById('city-input').value = '';
    document.getElementById('weather-result').textContent = '';
    document.getElementById('toggle-mode-btn').textContent = 'Автоматическое определение';
    document.getElementById('city-input').classList.add('hidden');
}

function toggleMode() {
    const modeBtn = document.getElementById('toggle-mode-btn');
    const cityInput = document.getElementById('city-input');

    mode = mode === 'auto' ? 'manual' : 'auto';
    modeBtn.textContent = mode === 'auto' ? 'Ввести город вручную' : 'Автоматическое определение';
    cityInput.classList.toggle('hidden');
}

async function getWeather() {
    const cityInput = document.getElementById('city-input');
    const resultArea = document.getElementById('weather-result');
    let city = null;

    if (mode === 'manual') {
        city = cityInput.value.trim();
        if (!city) {
            alert("Введите название города.");
            return;
        }
        city = city.charAt(0).toUpperCase() + city.slice(1).toLowerCase();
    }

    try {
        const userInfo = await getUserInfo();
        const params = { q: city, ...userInfo }

        const encryptedParams = encryptedClient.encryptRequest(params);

        const hmacSignature = generateHmac(encryptedParams);

        const response = await fetch(`http://127.0.0.1:5000/get_weather?${new URLSearchParams(encryptedParams)}`, {
            headers: { 'X-HMAC-Signature': hmacSignature }
        });

        if (!response.ok) throw new Error(`Ошибка HTTP: ${response.status}`);

        const encryptedData = await response.json();
        const data = encryptedClient.decryptResponse(encryptedData);

        if (data.error) {
            resultArea.textContent = `Ошибка: ${data.error}`;
        } else {
            resultArea.innerHTML = `
                Погода в ${data.city}, ${data.country}:<br>
                Температура: ${data.temperature}°C<br>
                Ощущается как: ${data.feels_like}°C<br>
                Влажность: ${data.humidity}%<br>
                Давление: ${data.pressure} hPa<br>
                Скорость ветра: ${data.wind_speed} м/с<br>
                Описание: ${data.description}
            `;
        }
    } catch (error) {
        resultArea.textContent = `Ошибка: ${error.message}`;
    }
}

async function getUserInfo() {
    try {
        const ipResponse = await fetch('https://api.ipify.org?format=json');
        const ipData = await ipResponse.json();

        return {
            ip: ipData.ip,
            userAgent: navigator.userAgent,
            language: navigator.language,
            platform: navigator.platform,
            screenWidth: window.screen.width,
            screenHeight: window.screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            cookiesEnabled: navigator.cookieEnabled,
            online: navigator.onLine,
            deviceMemory: navigator.deviceMemory || 'unknown',
            hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
        };
    } catch (error) {
        console.error("Ошибка получения информации о пользователе:", error);
        return {};
    }
}

function showSearchDialog(type) {
    closeAllDialogs();
    const dialog = document.getElementById('search-dialog');
    dialog.classList.remove('hidden');

    document.getElementById('search-input').value = '';
    document.getElementById('search-results').innerHTML = '';

    const titles = {
        products: 'Поиск товаров',
        food: 'Поиск продуктов',
        web: 'Веб-поиск'
    };
    document.getElementById('search-title').textContent = titles[type];
    currentSearchType = type;
}

async function doSearch() {
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');
    const query = input.value.trim();

    if (!query) {
        alert("Введите поисковый запрос");
        return;
    }

    try {
        const userInfo = await getUserInfo();
        const params = { query, ...userInfo };

        const encryptedParams = encryptedClient.encryptRequest(params);

        const hmacSignature = generateHmac(encryptedParams);

        const endpoint = currentSearchType === 'places'
            ? `search_places?${new URLSearchParams(encryptedParams)}`
            : `search_${currentSearchType}?${new URLSearchParams(encryptedParams)}`;

        const response = await fetch(`http://127.0.0.1:5000/${endpoint}`, {
            headers: { 'X-HMAC-Signature': hmacSignature }
        });

        if (!response.ok) throw new Error(`Ошибка HTTP: ${response.status}`);

        const encryptedData = await response.json();
        const data = encryptedClient.decryptResponse(encryptedData);

        results.innerHTML = data.error
            ? `Ошибка: ${data.error}`
            : Object.entries(data).map(([key, val]) => `<p>${key}: <a href="${val}" target="_blank">${val}</a></p>`).join('');
    } catch (error) {
        results.textContent = `Ошибка: ${error.message}`;
    }
}

async function handlePlaces(type) {
    closeAllDialogs();
    try {
        const coords = await getCurrentLocation();
        const userInfo = await getUserInfo();
        const params = { lat: coords.latitude, lon: coords.longitude, ...userInfo };

        const encryptedParams = encryptedClient.encryptRequest(params);

        const hmacSignature = generateHmac(encryptedParams);

        const response = await fetch(`http://127.0.0.1:5000/find_${type}?${new URLSearchParams(encryptedParams)}`, {
            headers: { 'X-HMAC-Signature': hmacSignature }
        });

        if (!response.ok) throw new Error(`Ошибка HTTP: ${response.status}`);

        const encryptedData = await response.json();
        const data = encryptedClient.decryptResponse(encryptedData);

        data.error ? alert(data.error) : displayResults(type === 'restaurants' ? 'Рестораны' : 'Отели', data);
    } catch (error) {
        alert(`Ошибка: ${error.message}`);
    }
}

async function handleAddress() {
    closeAllDialogs();
    try {
        const coords = await getCurrentLocation();
        const userInfo = await getUserInfo();
        const params = { lat: coords.latitude, lon: coords.longitude, ...userInfo };

        const encryptedParams = encryptedClient.encryptRequest(params);

        const hmacSignature = generateHmac(encryptedParams);

        const response = await fetch(`http://127.0.0.1:5000/get_address?${new URLSearchParams(encryptedParams)}`, {
            headers: { 'X-HMAC-Signature': hmacSignature }
        });

        if (!response.ok) throw new Error(`Ошибка HTTP: ${response.status}`);

        const encryptedData = await response.json();
        const data = encryptedClient.decryptResponse(encryptedData);

        data.error
            ? alert(data.error)
            : displayResults('Адрес', { Адрес: data.address, Карта: data.map_link });
    } catch (error) {
        alert(`Ошибка: ${error.message}`);
    }
}

function showPlacesSearchDialog() {
    closeAllDialogs();
    const dialog = document.getElementById('search-dialog');

    document.getElementById('search-input').value = '';
    document.getElementById('search-results').innerHTML = '';

    dialog.classList.remove('hidden');
    document.getElementById('search-title').textContent = 'Поиск мест';
    currentSearchType = 'places';
}

function showExactSearchDialog() {
    closeAllDialogs();
    const dialog = document.getElementById('search-dialog');

    document.getElementById('search-input').value = '';
    document.getElementById('search-results').innerHTML = '';

    dialog.classList.remove('hidden');
    document.getElementById('search-title').textContent = 'Точный поиск';
    currentSearchType = 'exact';
}

function displayResults(title, data) {
    closeAllDialogs();
    const dialog = document.getElementById('result-dialog');
    const content = document.getElementById('result-content');

    document.getElementById('result-title').textContent = title;
    content.innerHTML = '';

    if (Array.isArray(data)) {
        content.innerHTML = data.map(item => `
            <div class="result-item">
                <strong>${item.name || 'Без названия'}</strong>
                <p>Адрес: ${item.address || 'Нет данных'}</p>
                <p>Рейтинг: ${item.rating || 'Н/Д'}</p>
                <a href="${item.map_link}" target="_blank">Посмотреть на карте</a>
            </div>
        `).join('<hr>');
    } else {
        content.innerHTML = Object.entries(data).map(([key, val]) => `
            <p><strong>${key}:</strong> ${val || 'Нет данных'}</p>
        `).join('');
    }

    dialog.classList.remove('hidden');
}

async function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("Геолокация не поддерживается вашим браузером"));
        } else {
            navigator.geolocation.getCurrentPosition(
                position => resolve(position.coords),
                error => reject(new Error("Не удалось определить местоположение"))
            );
        }
    });
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('.dialog') && !e.target.closest('button')) {
        closeAllDialogs();
    }
});
