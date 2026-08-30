import asyncio
import datetime
import json
import os
import urllib.parse
import base64
from aiohttp import web, ClientSession

# --- НАСТРОЙКИ ---
OUTPUT_FILE = "subscription.txt"
CHECK_INTERVAL = 3600  # Проверка каждый час (3600 секунд)
TIMEOUT = 3.0  # Тайм-аут TCP-соединения

# Ваши источники конфигураций
SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS%2BAll_RUS.txt",
    "https://sub.vlessfo.ru/vlessforu/working_configs.txt",
    "https://ws-sub-hub.sos.al/sub/razlo4ka7",
    "https://ws-sub-hub.sos.al/sub/kafka_def",
    "https://ws-sub-hub.sos.al/sub/VanekVPN"
]

def parse_proxy_link(link):
    """Извлекает host и port из vless, vmess, ss, trojan, полностью очищая от названий."""
    try:
        base_link = link.split("#")[0].strip()

        if base_link.startswith("vmess://"):
            b64_data = base64.b64decode(base_link[8:]).decode("utf-8")
            config = json.loads(b64_data)
            return config.get("add"), int(config.get("port")), base_link

        elif base_link.startswith(("vless://", "trojan://", "ss://")):
            parsed = urllib.parse.urlparse(base_link)
            netloc = parsed.netloc
            if "@" in netloc:
                netloc = netloc.split("@")[-1]

            if ":" in netloc:
                host, port = netloc.split(":")
                port = int(port.split("?")[0])
                return host, port, base_link
    except Exception:
        pass
    return None, None, None

async def check_tcp(host, port):
    """Асинхронная проверка доступности TCP-порта серверов."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

def try_decode_base64(text):
    """Проверяет, зашифрован ли текст в Base64, и декодирует его, если нужно."""
    text = text.strip()
    # Пытаемся декодировать, если текст похож на Base64 без пробелов
    if text and not any(proto in text for proto in ["vless://", "vmess://", "ss://", "trojan://"]):
        try:
            # Исправляем возможное отсутствие паддинга (=) в Base64
            padded_text = text + "=" * ((4 - len(text) % 4) % 4)
            decoded = base64.b64decode(padded_text).decode("utf-8", errors="ignore")
            if any(proto in decoded for proto in ["vless://", "vmess://", "ss://", "trojan://"]):
                return decoded
        except Exception:
            pass
    return text

async def fetch_sources():
    """Автоматически скачивает, распознает Base64 и собирает все ключи из сети."""
    raw_keys = set()
    async with ClientSession() as session:
        for url in SOURCES:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # Проверяем на Base64 шифрование подписки
                        processed_text = try_decode_base64(text)
                        
                        for line in processed_text.splitlines():
                            line = line.strip()
                            if line.startswith(("vless://", "vmess://", "ss://", "trojan://")):
                                raw_keys.add(line)
            except Exception as e:
                print(f"Ошибка скачивания из источника {url}: {e}")
    return list(raw_keys)

async def run_checker():
    """Периодический таск: собирает, проверяет и полностью перезаписывает подписку."""
    while True:
        print(f"[{datetime.datetime.now()}] Старт автоматического сбора конфигов...")
        
        lines = await fetch_sources()
        print(f"Всего получено {len(lines)} уникальных ключей для проверки.")

        current_date = datetime.datetime.now().strftime("%d.%m.%y")

        # Наша шапка профиля (без отзывов, announce в одну строчку)
        header = (
            f"#profile-title: Обход Ура\n"
            f"#support-url:https://t.me\n"
            f"#info-url:https://netlify.app\n"
            f"#profile-update-interval: 1\n"
            f"#announce: Для добавления вашего ключа в подписку, напишите нам в поддержку. 📅 Обновлено: {current_date}\n\n"
        )

        valid_keys = []

        for line in lines:
            host, port, clean_link = parse_proxy_link(line)
            if not host or not port:
                continue

            is_alive = await check_tcp(host, port)
            if is_alive:
                # В подписку попадает строго очищенный рабочий ключ
                valid_keys.append(f"{clean_link}\n")

        # Принудительное опустошение ('w') и запись только живых прокси
        try:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
                out.write(header + "".join(valid_keys))
            print(f"Подписка обновлена. Старые данные стерты. Найдено живых: {len(valid_keys)}")
        except Exception as e:
            print(f"Ошибка записи в {OUTPUT_FILE}: {e}")

        # Засыпаем на 1 час
        await asyncio.sleep(CHECK_INTERVAL)

async def handle_sub_request(request):
    """Отдает итоговый очищенный файл подписки клиентам по HTTP."""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/plain; charset=utf-8")
    return web.Response(text="Подписка генерируется, пожалуйста, подождите...", status=503)

async def init_app():
    """Инициализация веб-сервера."""
    app = web.Application()
    app.router.add_get("/", handle_sub_request)
    app.router.add_get("/sub", handle_sub_request)

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Веб-сервер подписок успешно запущен на порту {port}")

async def main():
    await init_app()
    await run_checker()

if __name__ == "__main__":
    asyncio.run(main())
  
