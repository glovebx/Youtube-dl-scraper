# youtube_dl_scraper/site_scrapers/caption_scrapers/downsub.py
import json
import requests
from langcodes import find as find_language
from youtube_dl_scraper.core.caption_array import CaptionArray
from youtube_dl_scraper.core.base_scraper import BaseScraper
from youtube_dl_scraper.core.exceptions import (
    YouTubeDLScraperError,
    ScraperExecutionError,
    PlaywrightError,
    CaptionsNotFoundError,
)
from youtube_dl_scraper.utils.playwright_runner import Playwright
from  playwright.async_api import async_playwright, Response, Error as PlaywrightError
import asyncio
from youtube_dl_scraper.utils.json_to_srt import json_to_srt


class NoteGpt(BaseScraper):
    """A scraper wrapper for notegpt.io"""

    # meta data
    __name__ = "NoteGpt"
    __type__ = "caption"
    __host__ = "notegpt.io"

    def scrape_captions(self, url: str) -> dict:
        f"""scrape {self.__host__} to get a formatted dictionary of captions"""
        try:
            captured_response_data = asyncio.run(self.scrape_by_simulator(url))
            # print(f"captions_url: {captions_url}")
            if captured_response_data:
                return self.parse_caption_data(captured_response_data)
            else:
                raise YouTubeDLScraperError(
                    f"Failed to fetch captions: 'Unknown error'"
                )
        except PlaywrightError as e:
            raise ScraperExecutionError(f"Playwright Error occured: {str(e)}")

    # def process_response(self, caption_endpoint: str) -> dict:
    #     """fetch and processes data from the caption endpoint"""
    #     if not caption_endpoint:
    #         raise CaptionsNotFoundError("Caption endpoint is empty.")
    #     response = requests.get(caption_endpoint)
    #     if response.status_code == 200:
    #         data = response.json()
    #         return self.parse_caption_data(data) if data else None
    #     else:
    #         raise YouTubeDLScraperError(
    #             "Invalid response code: {}".format(response.status_code)
    #         )

    def parse_caption_data(self, response_data: dict) -> dict:
        """parse data from the caption endpoint to a general format"""

        captions_data = {}  # the formatted dictionary for caption data
        data = response_data.get("data")

        print(response_data)

        video_info = data.get("videoInfo")

        captions_data["title"] = video_info.get("name", "")
        thumbnail_urls = video_info.get("thumbnailUrl", {})
        captions_data["thumbnail"] = thumbnail_urls.get("hqdefault", "")
        captions_data["duration"] = video_info.get("duration")
        language_codes = data.get("language_code", [])

        captions_data["subtitles"] = []

        transcripts = data.get("transcripts")        
        for sub in language_codes:
        # for sub in data.get("subtitles", []):
            # sub["code"] = (
            #     "a." + str(find_language(sub["name"]))
            #     if "auto" in sub["code"]
            #     else sub["code"]
            # )
            code = sub["code"]
            lang_transcripts = transcripts[code]
            contents = lang_transcripts.get("default")
            if not contents:
                contents = lang_transcripts.get("auto")
            # 读取成text和srt两个数据 [{'text': body_text, 'srt': srt_text}]
            text = '\n'.join([x['text'] for x in contents])
            srt_text = "\n".join(json_to_srt(contents))
            sub["__contents"] = [{'text': text, 'srt': srt_text}]
            sub["urls"] = {}

            sub["code"] = (
                "a." + code.split("_")[0]
                if "_auto" in code
                else code
            )
                        
            captions_data["subtitles"].append(sub)

        # # captions_data["translations"] = []
        # # for sub in data.get("transcripts", []):
        # #     sub["code"] = str(find_language(sub["name"]))  # fetch lang code
        # #     captions_data["translations"].append(sub)
        # # # add more formating to include dowload url for each formart i.e. srt, txt, raw
        # # translation_types = ("subtitles", "translations")

        # transcripts = data.get("transcripts")
        # for lang in language_codes:
        #     lang_transcripts = transcripts[lang]  # subtitle dict
        #     captions_data["subtitles"]
        #     for sub in lang_transcripts:  # for subtitle in subtitles
        #         captions_data["subtitles"]
        # # print(captions_data)
        return captions_data

    async def scrape_by_simulator(self, url: str):
        self.captured_response_data = ''
        async with async_playwright() as pr:
            browsers = {
                "chromium": pr.chromium,
                "webkit": pr.webkit,
                "firefox": pr.firefox
            }
            # browser_name = random.choice(["chromium", "webkit", "firefox"])
            browser_name = "chromium" # using firedox bacause it dosen't get flaged by cloudfare
            browser_type = browsers[browser_name]
            # print(browser_name)
            browser = await browser_type.launch()
            context = await browser.new_context()
            page = await context.new_page()
            
            # caption_data = {'url': str()}
            
            async def caption_api_route_handler(route, request):
                # response = await route.fetch(headers={'Accept': 'application/json;charset=UTF-8', 'Accept-Charset': 'UTF-8'})
                
                # print("Page 5555555")
                # First, fetch the actual response for the request
                response: Response = await route.fetch(
                    headers={
                        'Accept': 'application/json;charset=UTF-8',
                        'Accept-Charset': 'UTF-8'
                    }
                )

                # print("Page 6666666")
                # Now, process the response
                if response:
                    # print(f"Response URL: {response.url}")
                    # print(f"Response Status: {response.status}")
                    # print(f"Response Headers: {response.headers}")

                    # Try to get the response body as JSON
                    try:
                        response_json = await response.json()
                        self.captured_response_data = response_json
                        # print(f"Response JSON Data: {json.dumps(response_json, indent=2)[:100]}")
                    except Exception as e:
                        print(f"Could not parse response as JSON: {e}")
                        # If not JSON, try to get it as plain text
                        try:
                            response_text = await response.text()
                            self.captured_response_data = response_text
                            # print(f"Response Text Data: {response_text[:100]}...") # Print first 500 chars
                        except Exception as e_text:
                            print(f"Could not get response as text: {e_text}")
                else:
                    print("No response received for this request.")

                await route.abort()
                # await page.screenshot(path="collected.png")
                await page.close()
            
            await page.route('https://notegpt.io/api/v2/video-transcript?*', caption_api_route_handler)
            # await context.route("**/a.clarity.ms/**", lambda route: route.abort())
            # await context.route("**/challenges.cloudflare.com/**", lambda route: route.abort())
            try:
                await page.goto(f'https://notegpt.io/youtube-subtitle-downloader', timeout=86400000, wait_until='domcontentloaded')
                # await page.screenshot(path="loaded.png")

                input_selector = '#app > div.grid-content > div > div.ng-script > div > div.script-youtube-2_main > div.ng-script-input.el-input > input'
                button_selector = "#app > div.grid-content > div > div.ng-script > div > div.script-youtube-2_main > button.el-button.ng-script-btn.el-button--success > span"
                await page.wait_for_selector(input_selector, state='visible')

                # 填入url
                await page.fill(input_selector, url)

                await page.click(button_selector)

                try:
                    await page.wait_for_timeout(60000)
                except:
                    pass    
            except PlaywrightError as e:
                if "Page.wait_for_selector: Target page, context or browser has been closed" in str(e):
                    print("Page has been closed properly")
                elif "Timeout" in str(e):
                    print("Page taking too long to load")
                else:
                    print("Page load error")
                    print(e)
                    raise e
            finally:
                try:
                    await context.close()
                    await browser.close()
                except:
                    pass

        return self.captured_response_data        