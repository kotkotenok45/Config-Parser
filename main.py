import asyncio
import datetime
import json
import urllib.parse
import base64
import aiohttp

OUTPUT_FILE = "subscription.txt"
TIMEOUT = 3.0

SOURCES = [
    "https://githubusercontent.com",
    "https://vlessfo.ru",
    "https://sos.al",
    "https://sos.al",
    "https://sos.al"
]

def parse_proxy_link(link):
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
    except:
        pass
    return None, None, None

async def check_tcp(host, port):
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=TIMEOUT)
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

def try_decode_base64(text):
    text = text.strip()
    if text and not any(proto in text for proto in ["vless://", "vmess://", "ss://", "trojan://"]):
        try:
            padded_text = text + "=" * ((4 - len(text) % 4) % 4)
            decoded = base64.b64decode(padded_text).decode("utf-8", errors="ignore")
            if any(proto in decoded for proto in ["vless://", "vmess://", "ss://", "trojan://"]):
                return decoded
        except:
            pass
    return text

async def main():
    raw_keys = set()
    async with aiohttp.ClientSession() as session:
        for url in SOURCES:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, headers=headers, timeout=15) as res:
                    if res.status == 200:
                        text = await res.text()
                        processed = try_decode_base64(text)
                        for line in processed.splitlines():
                            line = line.strip()
                            if line.startswith(("vless://", "vmess://", "ss://", "trojan://")):
                                raw_keys.add(line)
            except Exception as e:
                print(f"Ошибка {url}: {e}")

    current_date = datetime.datetime.now().strftime("%d.%m.%y")
    header = (
        f"#profile-title: Обход Ура\n"
        f"#support-url:https://t.me\n"
        f"#info-url:https://netlify.app\n"
        f"#profile-update-interval: 1\n"
        f"#announce: Для добавления вашего ключа в подписку, напишите нам в поддержку. 📅 Обновлено: {current_date}\n\n"
    )

    valid_keys = []
    for line in raw_keys:
        host, port, clean_link = parse_proxy_link(line)
        if host and port and await check_tcp(host, port):
            valid_keys.append(f"{clean_link}\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(header + "".join(valid_keys))
    print(f"Записано рабочих ключей: {len(valid_keys)}")

if __name__ == "__main__":
    asyncio.run(main())
        
