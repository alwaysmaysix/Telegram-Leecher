import logging
import yt_dlp
from asyncio import sleep
from threading import Thread
from os import makedirs, path as ospath, remove
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import YTDL, MSG, Messages, Paths
from colab_leecher.utility.helper import getTime, keyboard, sizeUnit, status_bar, sysINFO
import json
import google_colab_selenium as gs
from selenium.webdriver.chrome.options import Options
from random import choice
import time

# Load browsers.json for user agents and headers
def load_browsers_json():
    with open('/content/Telegram-Leecher/colab_leecher/browsers.json', 'r') as file:
        return json.load(file)

browsers_config = load_browsers_json()

def select_random_user_agent_and_headers():
    platform = choice(['desktop', 'mobile'])
    browser = choice(['chrome', 'firefox'])
    os_choice = choice(['windows', 'linux', 'darwin']) if platform == 'desktop' else choice(['android', 'ios'])
    user_agent = browsers_config['user_agents'][platform][os_choice][browser]
    headers = browsers_config['headers'][browser]
    return user_agent, headers

def setup_selenium():
    user_agent, headers = select_random_user_agent_and_headers()
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f'--user-agent={user_agent}')
    for key, value in headers.items():
        options.add_argument(f'--{key.lower()}={value}')
    driver = gs.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver, user_agent, headers

def handle_cloudflare_challenge(driver, timeout=30):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.title != "Just a moment..." and "challenge" not in d.current_url
        )
    except TimeoutException:
        raise Exception("Cloudflare challenge timed out")

def YouTubeDL(url):
    global YTDL
    driver, user_agent, headers = setup_selenium()
    try:
        driver.get(url)
        handle_cloudflare_challenge(driver)
        time.sleep(5)  # Additional delay to ensure page load
        
        # Save cookies for yt-dlp
        cookies = driver.get_cookies()
        cookie_file = "ytdl_cookies.txt"
        with open(cookie_file, 'w') as f:
            for cookie in cookies:
                f.write(f"{cookie['name']}={cookie['value']}; Domain={cookie['domain']}; Path={cookie['path']}\n")
        
        # Configure yt-dlp with cookies and headers
        ydl_opts = {
            "format": "bestvideo[height<=360]+bestaudio/worst",
            "cookiefile": cookie_file,
            "http_headers": headers,
            "user_agent": user_agent,
            "allow_multiple_video_streams": True,
            "allow_multiple_audio_streams": True,
            "writethumbnail": True,
            "concurrent-fragments": 4,
            "allow_playlist_files": True,
            "overwrites": True,
            "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            "progress_hooks": [my_hook],
            "writesubtitles": "srt",
            "extractor_args": {"subtitlesformat": "srt"},
            "logger": MyLogger(),
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if not ospath.exists(Paths.thumbnail_ytdl):
                makedirs(Paths.thumbnail_ytdl)
            info_dict = ydl.extract_info(url, download=False)
            YTDL.header = "⌛ __Please WAIT a bit...__"
            if "_type" in info_dict and info_dict["_type"] == "playlist":
                playlist_name = info_dict["title"]
                if not ospath.exists(ospath.join(Paths.down_path, playlist_name)):
                    makedirs(ospath.join(Paths.down_path, playlist_name))
                ydl_opts["outtmpl"] = {
                    "default": f"{Paths.down_path}/{playlist_name}/%(title)s.%(ext)s",
                    "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                }
                for entry in info_dict["entries"]:
                    video_url = entry["webpage_url"]
                    try:
                        ydl.download([video_url])
                    except yt_dlp.utils.DownloadError as e:
                        if e.exc_info[0] == 36:
                            ydl_opts["outtmpl"] = {
                                "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                                "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                            }
                            ydl.download([video_url])
            else:
                YTDL.header = ""
                ydl_opts["outtmpl"] = {
                    "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                    "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                }
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as e:
                    if e.exc_info[0] == 36:
                        ydl_opts["outtmpl"] = {
                            "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                            "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                        }
                        ydl.download([url])
    except Exception as e:
        logging.error(f"YTDL ERROR: {e}")
    finally:
        driver.quit()
        if ospath.exists(cookie_file):
            remove(cookie_file)  # Clean up cookies file

async def YTDL_Status(link, num):
    global Messages, YTDL
    name = await get_YT_Name(link)
    Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

    # Start the Selenium-based download in a separate thread
    YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link,))
    YTDL_Thread.start()

    while YTDL_Thread.is_alive():
        if YTDL.header:
            sys_text = sysINFO()
            message = YTDL.header
            try:
                await MSG.status_msg.edit_text(text=Messages.task_msg + Messages.status_head + message + sys_text, reply_markup=keyboard())
            except Exception:
                pass
        else:
            try:
                await status_bar(
                    down_msg=Messages.status_head,
                    speed=YTDL.speed,
                    percentage=float(YTDL.percentage),
                    eta=YTDL.eta,
                    done=YTDL.done,
                    left=YTDL.left,
                    engine="Xr-YtDL 🏮",
                )
            except Exception:
                pass

        await sleep(2.5)

class MyLogger:
    def __init__(self):
        pass

    def debug(self, msg):
        global YTDL
        if "item" in str(msg):
            msgs = msg.split(" ")
            YTDL.header = f"\n⏳ __Getting Video Information {msgs[-3]} of {msgs[-1]}__"

    @staticmethod
    def warning(msg):
        pass

    @staticmethod
    def error(msg):
        # if msg != "ERROR: Cancelling...":
        # print(msg)
        pass

async def get_YT_Name(link):
    with yt_dlp.YoutubeDL({"logger": MyLogger()}) as ydl:
        try:
            info = ydl.extract_info(link, download=False)
            if "title" in info and info["title"]: 
                return info["title"]
            else:
                return "UNKNOWN DOWNLOAD NAME"
        except Exception as e:
            await cancelTask(f"Can't Download from this link. Because: {str(e)}")
            return "UNKNOWN DOWNLOAD NAME"
