import hashlib
import os
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

URL = "https://hyroxdach.com/de/event/fitness-first-hyrox-frankfurt/"
HASH_FILE = "last_hash.txt"
SCREENSHOT_FILE = "screenshot.png"


def get_page_content_and_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # Warten bis JS fertig gerendert hat

        # Cookie-Banner wegklicken (verschiedene mögliche Texte/Selektoren)
        for selector in [
            "button:has-text('Akzeptieren')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "button:has-text('Zustimmen')",
            "[id*='cookie'] button",
            "[class*='cookie'] button",
            "[class*='consent'] button",
        ]:
            try:
                page.click(selector, timeout=1500)
                page.wait_for_timeout(500)
                break
            except Exception:
                pass

        page.wait_for_timeout(1000)
        content = page.inner_text("body")
        page.screenshot(path=SCREENSHOT_FILE, full_page=True)
        browser.close()
    return content


def compute_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def load_last_hash() -> str:
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            return f.read().strip()
    return ""


def save_hash(hash_value: str):
    with open(HASH_FILE, "w") as f:
        f.write(hash_value)


def send_ntfy(screenshot_path: str):
    topic = os.environ["NTFY_TOPIC"]
    with open(screenshot_path, "rb") as f:
        response = requests.put(
            f"https://ntfy.sh/{topic}",
            data=f,
            headers={
                "Title": "Hyrox Frankfurt - Seite geaendert!",
                "Message": f"Schnell anmelden! {URL}",
                "Filename": "screenshot.png",
                "Click": URL,
                "Priority": "urgent",
                "Tags": "rotating_light,ticket",
            },
        )
    response.raise_for_status()


def send_email(screenshot_path: str):
    sender = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("NOTIFY_EMAIL", sender)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Hyrox Frankfurt - Seite hat sich geaendert!"

    body = (
        "Die Hyrox-Website hat sich geaendert - moeglicherweise sind Tickets verfuegbar!\n\n"
        f"Jetzt anmelden: {URL}\n\n"
        "Screenshot im Anhang."
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(screenshot_path, "rb") as f:
        img = MIMEImage(f.read())
        img.add_header("Content-Disposition", "attachment", filename="screenshot.png")
        msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, recipient, msg.as_string())


def main():
    print(f"Pruefe {URL} ...")

    content = get_page_content_and_screenshot()
    current_hash = compute_hash(content)
    last_hash = load_last_hash()

    print(f"Aktueller Hash : {current_hash}")
    print(f"Letzter Hash   : {last_hash}")

    if not last_hash:
        print("Erster Aufruf - speichere initialen Hash.")
        save_hash(current_hash)
        return

    if current_hash != last_hash:
        print("AENDERUNG ERKANNT! Sende Benachrichtigungen ...")
        save_hash(current_hash)

        try:
            send_ntfy(SCREENSHOT_FILE)
            print("ntfy-Benachrichtigung gesendet.")
        except Exception as e:
            print(f"ntfy-Fehler: {e}")

        try:
            send_email(SCREENSHOT_FILE)
            print("E-Mail gesendet.")
        except Exception as e:
            print(f"E-Mail-Fehler: {e}")
    else:
        print("Keine Aenderung festgestellt.")


if __name__ == "__main__":
    main()
