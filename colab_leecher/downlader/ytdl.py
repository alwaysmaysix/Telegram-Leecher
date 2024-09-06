# copyright 2023 © Xron Trix | https://github.com/Xrontrix10

import logging
import yt_dlp
from asyncio import sleep
from threading import Thread
from os import makedirs, path as ospath
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import YTDL, MSG, Messages, Paths
from colab_leecher.utility.helper import getTime, keyboard, sizeUnit, status_bar, sysINFO
import json
import google_colab_selenium as gs
from selenium.webdriver.chrome.options import Options
from random import choice
import time

# Load the browsers.json file
def load_browsers_json():
    with open('/content/colab_leecher/browsers.json', 'r') as file:
        return json.load(file)

browsers_config = load_browsers_json()

# Function to choose a random user agent and corresponding headers
def select_random_user_agent_and_headers():
    platform = choice(['desktop', 'mobile'])
    browser = choice(['chrome', 'firefox'])
    
    if platform == 'desktop':
        os_choice = choice(['windows', 'linux', 'darwin'])
    else:
        os_choice = choice(['android', 'ios'])

    user_agent = browsers_config['user_agents'][platform][os_choice][browser]
    headers = browsers_config['headers'][browser]
    
    return user_agent, headers

# Setup Selenium with undetected Chrome and mimic real user behavior
def setup_selenium():
    user_agent, headers = select_random_user_agent_and_headers()
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--incognito")
    options.add_argument(f'--user-agent={user_agent}')
    
    for key, value in headers.items():
        options.add_argument(f'--{key.lower()}={value}')
    
    driver = gs.Chrome(options=options)
    return driver

# Retrieve page content with Selenium
def get_page_content(url, driver, request_interval=2, page_load_delay=2):
    driver.get(url)
    time.sleep(request_interval)
    html_content = driver.page_source
    time.sleep(page_load_delay)
    return html_content

# Modified YouTubeDL function to use Selenium for Cloudflare handling
def YouTubeDL(url):
    global YTDL

    def my_hook(d):
        global YTDL

        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes", 0)
            dl_bytes = d.get("downloaded_bytes", 0)
            percent = d.get("downloaded_percent", 0)
            speed = d.get("speed", "N/A")
            eta = d.get("eta", 0)

            if total_bytes:
                percent = round((float(dl_bytes) * 100 / float(total_bytes)), 2)

            YTDL.header = ""
            YTDL.speed = sizeUnit(speed) if speed else "N/A"
            YTDL.percentage = percent
            YTDL.eta = getTime(eta) if eta else "N/A"
            YTDL.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
            YTDL.left = sizeUnit(total_bytes) if total_bytes else "N/A"

        elif d["status"] == "downloading fragment":
            pass
        else:
            logging.info(d)

    # Initialize Selenium and retrieve page content
    driver = setup_selenium()
    html_content = get_page_content(url, driver)

    ydl_opts = {
        "format": "bestvideo[height<=360]+bestaudio/worst",
        "allow_multiple_video_streams": True,
        "allow_multiple audio_streams": True,
        "writethumbnail": True,
        "--concurrent-fragments": 4,
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
        try:
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
