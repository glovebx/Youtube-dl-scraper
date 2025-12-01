# youtube_dl_scraper/site_scrapers/caption_scrapers/downsub.py
import re
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
import urllib.parse

payload = """
# import random
from  playwright.async_api import async_playwright, Error as PlaywrightError
import asyncio

async def main():
    async with async_playwright() as pr:
        browsers = {
            "chromium": pr.chromium,
            "webkit": pr.webkit,
            "firefox": pr.firefox
        }
        # browser_name = random.choice(["chromium", "webkit", "firefox"])
        browser_name = "firefox" # using firedox bacause it dosen't get flaged by cloudfare
        browser_type = browsers[browser_name]
        print(browser_name)
        browser = await browser_type.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        caption_data = {'url': str()}
        
        async def caption_api_route_handler(route, request):
            # response = await route.fetch(headers={'Accept': 'application/json;charset=UTF-8', 'Accept-Charset': 'UTF-8'})
            
            caption_data['url'] = request.url
            print('{{' + caption_data['url'] + '}}')
            await route.abort()
            await page.screenshot(path="collected.png")
            await page.close()
        
        await page.route('https://get-info.downsub.com/*', caption_api_route_handler)
        await context.route("**/*ads**", lambda route: route.abort())
        try:
            await page.goto(f'https://downsub.com?url={url}', timeout=86400000, wait_until='domcontentloaded')
            await page.screenshot(path="loaded.png")
            await page.wait_for_selector('#app > div > main > div > div.container.ds-info.outlined > div > div.row.no-gutters > div.pr-1.col-sm-7.col-md-6.col-12 > div.v-card.v-card --flat.v-sheet.theme--light > div.d-flex.flex-no-wrap.justify-start > div.ma-0.m t-2.text-center > a > div > div.v-responsive__content')
        except PlaywrightError as e:
            if "Page.wait_for_selector: Target page, context or browser has been closed" in str(e) or "Timeout" in str(e):
                print("Page taking too long to load")
            else:
                raise e
        finally:
          try:
              await context.close()
              await browser.close()
          except:
              pass

asyncio.run(main())
"""


class DownSub(BaseScraper):
    """A scraper wrapper for downsub.com"""

    # meta data
    __name__ = "DownSub"
    __type__ = "caption"
    __host__ = "downsub.com"

    def generate_payload(self, url: str) -> str:
        """generate payload to fetch caption endpoint"""
        return f"url = '{url}'\n" + payload

    def scrape_captions(self, url: str) -> dict:
        f"""scrape {self.__host__} to get a formatted dictionary of captions"""
        try:
            # captions_url = asyncio.run(self.scrape_by_hook(url))
            # # print(f"captions_url: {captions_url}")
            # if captions_url:
            #     return self.process_response(captions_url)
            # else:
            captured_response_data = asyncio.run(self.scrape_by_simulator(url))
            if captured_response_data:
                captured_response_data["thumbnail"] = ""
                captured_response_data["duration"] = ""

                return captured_response_data

            raise YouTubeDLScraperError(
                f"Failed to fetch captions: 'Unknown error'"
            )
            
            # response = Playwright().run(self.generate_payload(url))
            # if response.get("success") and response.get("status_code") == 200:
            #     caption_endpoint_match = re.search(
            #         r"\{\{(.+)\}\}", response.get("output", "")
            #     )
            #     if caption_endpoint_match:
            #         caption_endpoint = caption_endpoint_match.group(1)
            #         return self.process_response(caption_endpoint)
            #     else:
            #         raise CaptionsNotFoundError("No captions found in response.")
            # else:
            #     raise YouTubeDLScraperError(
            #         f"Failed to fetch captions: {response.get('error', 'Unknown error')}"
            #     )
        except PlaywrightError as e:
            raise ScraperExecutionError(f"Playwright Error occured: {str(e)}")

    def process_response(self, caption_endpoint: str) -> dict:
        """fetch and processes data from the caption endpoint"""
        if not caption_endpoint:
            raise CaptionsNotFoundError("Caption endpoint is empty.")
        response = requests.get(caption_endpoint)
        if response.status_code == 200:
            data = response.json()
            return self.parse_caption_data(data) if data else None
        else:
            raise YouTubeDLScraperError(
                "Invalid response code: {}".format(response.status_code)
            )

    def parse_caption_data(self, data: dict) -> dict:
        """parse data from the caption endpoint to a general format"""
        if data.get("sourceName") != "Youtube":
            raise CaptionsNotFoundError("Capition found but invalid caption type")
        captions_data = {}  # the formatted dictionary for caption data
        dl_api = data.get("urlSubtitle")
        captions_data["title"] = data.get("title", "")
        captions_data["thumbnail"] = data.get("thumbnail", "")
        captions_data["duration"] = data.get("duration")
        captions_data["subtitles"] = []
        for sub in data.get("subtitles", []):
            sub["code"] = (
                "a." + str(find_language(sub["name"]))
                if "auto" in sub["code"]
                else sub["code"]
            )
            captions_data["subtitles"].append(sub)
        captions_data["translations"] = []
        for sub in data.get("subtitlesAutoTrans", []):
            sub["code"] = str(find_language(sub["name"]))  # fetch lang code
            captions_data["translations"].append(sub)
        # add more formating to include dowload url for each formart i.e. srt, txt, raw
        translation_types = ("subtitles", "translations")
        for t_type in translation_types:
            subs = captions_data[t_type]  # subtitle dict
            for sub in subs:  # for subtitle in subtitles
                sub["urls"] = {
                    "raw": f"{dl_api}?url={sub['url']}&type=raw&title={captions_data['title']}",
                    "txt": f"{dl_api}?url={sub['url']}&type=txt&title={captions_data['title']}",
                    "srt": f"{dl_api}?url={sub['url']}&title={captions_data['title']}",
                }
                sub.pop("url")

        # print(captions_data)
        return captions_data

    async def scrape_by_hook(self, url: str):
        self.captions_url = ''
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
            
            caption_data = {'url': str()}
            
            async def caption_api_route_handler(route, request):
                # response = await route.fetch(headers={'Accept': 'application/json;charset=UTF-8', 'Accept-Charset': 'UTF-8'})
                
                self.captions_url = request.url
                caption_data['url'] = request.url
                print('{{' + caption_data['url'] + '}}')
                await route.abort()
                # await page.screenshot(path="collected.png")
                await page.close()
            
            await page.route('https://get-info.downsub.com/*', caption_api_route_handler)
            await context.route("**/*ads**", lambda route: route.abort())
            try:
                await page.goto(f'https://downsub.com?url={url}', timeout=86400000, wait_until='domcontentloaded')
                # await page.screenshot(path="loaded.png")
                await page.wait_for_selector('#app > div > main > div > div.container.ds-info.outlined > div > div.row.no-gutters > div.pr-1.col-sm-7.col-md-6.col-12 > div.v-card.v-card --flat.v-sheet.theme--light > div.d-flex.flex-no-wrap.justify-start > div.ma-0.m t-2.text-center > a > div > div.v-responsive__content', timeout=60000)
            except PlaywrightError as e:
                if "Page.wait_for_selector: Target page, context or browser has been closed" in str(e):
                    print("Page has been closed properly")
                elif "Timeout" in str(e):
                    print("Page taking too long to load")
                else:
                    raise e
            finally:
                try:
                    await context.close()
                    await browser.close()
                except:
                    pass

        return self.captions_url
    
    def extract_title_from_url(self, url: str) -> str:
        """
        从给定的URL中提取标题。

        URL中的标题预计位于 'title' 参数中，并且是URL编码的。
        此函数使用urllib.parse来解析URL和查询字符串，
        然后提取并返回解码后的标题。

        Args:
            url: 包含编码后标题的URL字符串。

        Returns:
            解码后的标题字符串。
            如果URL中未找到 'title' 参数，则返回空字符串。
        """
        try:
            # 1. 解析URL
            parsed_url = urllib.parse.urlparse(url)

            # 2. 解析查询字符串
            query_params = urllib.parse.parse_qs(parsed_url.query)

            # 3. 从查询参数中获取标题
            #    parse_qs 返回一个字典，其中值是列表。
            #    我们取第一个元素，即使该参数多次出现。
            title_list = query_params.get('title', [])  # 默认返回空列表
            title = title_list[0] if title_list else ""  # 如果列表为空，则使用空字符串

            # 4. URL解码标题
            decoded_title = urllib.parse.unquote(title)

            return decoded_title

        except Exception as e:
            print(f"解析URL时发生错误: {e}")
            return ""  # 发生错误时返回空字符串
        
    async def scrape_by_simulator(self, url: str):
        self.captured_response_data = None
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
            # downsub似乎做了处理，必须要打开窗口
            browser = await browser_type.launch(
                    args=[
                        "--disable-web-security",
                        "--enable-font-antialiasing",
                        "--force-color-profile=srgb"
                    ]
            )
            context = await browser.new_context(accept_downloads=True,
                                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                                                viewport={"width": 1920, "height": 1080},
                                                locale="en-US",
                                                permissions=["clipboard-read"]
                                                )
            page = await context.new_page()
            
            # caption_data = {'url': str()}
            
            # async def caption_api_route_handler(route, request):
            #     # response = await route.fetch(headers={'Accept': 'application/json;charset=UTF-8', 'Accept-Charset': 'UTF-8'})

            #     print(f"Page 5555555 {request.url}")

            #     title = self.extract_title_from_url(request.url)

            #     response = requests.get(request.url)
            #     response.raise_for_status()

            #     response_text = response.text

            #     sub = {'code': 'a.en', 'name': 'English (auto-generated)', 'urls': {}, '__contents': [{'text': response_text}]}
            #     self.captured_response_data = {'title': title, 'subtitles': [sub]}

            #     # # First, fetch the actual response for the request
            #     # response: Response = await route.fetch(
            #     #     method='GET',
            #     #     headers={
            #     #         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            #     #         'Accept-Charset': 'UTF-8'
            #     #     }
            #     # )

            #     # print("Page 6666666")
            #     # # Now, process the response
            #     # if response:
            #     #     print(f"Response URL: {response.url}")
            #     #     # print(f"Response Status: {response.status}")
            #     #     # print(f"Response Headers: {response.headers}")
            #     #     title = self.extract_title_from_url(response.url)

            #     #     print("Page 6666667")
            #     #     # try to get it as plain text
            #     #     try:
            #     #         response_text = await response.text()
            #     #         sub = {'code': 'a.en', 'name': 'English (auto-generated)', '__contents': [{'text': response_text}]}
            #     #         self.captured_response_data = {'title': title, 'subtitles': [sub]}
            #     #         # print(f"Response Text Data: {response_text[:100]}...") # Print first 500 chars
            #     #     except Exception as e_text:
            #     #         print(f"Could not get response as text: {e_text}")
            #     # else:
            #     #     print("No response received for this request.")

            #     await route.abort()
            #     # await page.screenshot(path="collected.png")
            #     await page.close()
            
            # await page.route('https://download.subtitle.to*', caption_api_route_handler)
            try:
                await page.goto(f'https://downsub.com?url={url}', timeout=86400000, wait_until='domcontentloaded')
                # await page.screenshot(path="loaded.png")

                print(f"Page goto {url}")

                # SRT 按钮
                srt_selector = "#app > div > main > div > div.container.ds-info.outlined > div > div.row.no-gutters > div.pr-1.col-sm-7.col-md-6.col-12 > div.flex.mt-5.text-center > div.layout.justify-start.align-center > button:nth-child(1) > span > button > span"
                await page.wait_for_selector(srt_selector, state='visible')
        
                print("SRT button found")
                # 1. Start waiting for the download BEFORE clicking the button
                # This is crucial to ensure you don't miss the download event.
                async with page.expect_download() as download_info:
                    # 2. Click the element that triggers the download
                    await page.click(srt_selector)
                    print(f"Clicked selector: {srt_selector}. Waiting for download...")

                download = await download_info.value
                print(f"Download initiated: {download.suggested_filename}")

                # Wait for the download process to complete and get the path to the temporary file
                # This path is managed by Playwright and will be cleaned up automatically later.
                download_path = await download.path()
                
                srt_text = ''

                if download_path:
                    print(f"Temporary download path: {download_path}")
                    
                    # 3. Read the content from the temporary file path into bytes
                    with open(download_path, 'rb') as f: # 'rb' for read binary
                        content_bytes = f.read()

                    # 3. Get the path to the downloaded file
                    # By default, Playwright downloads to a temporary directory.
                    # We need to save it to a known temporary location if we want to read it.
                    # For reading into memory directly, you don't strictly need to save it,
                    # but it's good practice for debugging or if you later decide to save.

                    # Option A: Read directly into memory (most efficient for your use case)
                    # This is the recommended approach for getting the byte stream.
                    # content_bytes = await download.body()
                    print(f"Downloaded file size (bytes): {len(content_bytes)}")

                    # # Store the content in a variable
                    # locals()[output_variable_name] = content_bytes
                    # print(f"File content stored in variable '{output_variable_name}'.")

                    # Example: Decode and print if it's text (optional)
                    try:
                        srt_text = content_bytes.decode('utf-8')
                        # print("\n--- Decoded Content (first 500 chars) ---")
                        # print(srt_text[:200])
                        # print("--------------------------------------")
                    except UnicodeDecodeError:
                        print("Downloaded content is not UTF-8 decodable (likely binary).")

                # 4. Optional: If you want to save the file temporarily to disk for inspection
                # await download.save_as(f"/tmp/{download.suggested_filename}")
                # print(f"File saved to: /tmp/{download.suggested_filename}")

                # # You can now access the variable:
                # print(f"Content variable type: {type(locals()[output_variable_name])}")
                # # print(f"First 10 bytes of content: {locals()[output_variable_name][:10]}")

                # # 触发下载并捕获事件
                # # with page.expect_download(timeout=60000) as download_info:
                # page.click(srt_selector)
                # download = page.wait_for_event("download")  # 关键修改点
                
                # download = download_info.value

                # if download:
                #     print(f"下载状态：{download.failure() or '无错误'}")
                    
                # # 直接读取文件内容到内存变量
                # file_content = download.body()  # 返回bytes类型
                
                # # 打印内容信息
                # print(f"✅ 下载成功！文件大小：{len(file_content)} 字节")

                # print("文件内容预览（前200字节）：")
                # print(file_content[:200].decode('utf-8', errors='replace'))  # 安全解码
                # srt_text = file_content.decode('utf-8')
                # # 如果需要完整内容：
                # print(srt_text[:200])  # 安全解码

                # RAW 按钮
                raw_selector = "#app > div > main > div > div.container.ds-info.outlined > div > div.row.no-gutters > div.pr-1.col-sm-7.col-md-6.col-12 > div.flex.mt-5.text-center > div.layout.justify-start.align-center > button:nth-child(3) > span > button"
                await page.wait_for_selector(raw_selector, state='visible')

                print("RAW button found")
                # 点击
                await page.click(raw_selector)

                print("RAW button clicked")
                try:
                    await page.wait_for_timeout(10000)
                except:
                    pass

                # 获取当前页面的URL
                url = page.url
                print(f"当前页面URL: {url}")

                # 默认英文
                subtitle_code = 'a.en'
                subtitle_name = 'English (auto-generated)'
                title = self.extract_title_from_url(url).replace('[DownSub.com]', '').strip()
                if 'English (auto-generated)' in title:
                    title = title.replace('English (auto-generated)', '')
                if '[English]' in title:
                    title = title.replace('[English]', '')
                if 'Japanese (auto-generated)' in title:
                    title = title.replace('Japanese (auto-generated)', '')
                    subtitle_code = 'a.ja'
                    subtitle_name = 'Japanese (auto-generated)'
                if '[Japanese]' in title:
                    title = title.replace('[Japanese]', '')
                    subtitle_code = 'a.ja'
                    subtitle_name = 'Japanese (auto-generated)'
                # 获取当前页面body中的文本内容
                body_text = await page.inner_text('body')

                sub = {'code': subtitle_code, 'name': subtitle_name, 'urls': {}, '__contents': [{'text': body_text, 'srt': srt_text}]}
                self.captured_response_data = {'title': title, 'subtitles': [sub]}

                print(f"Subtitle downloading {subtitle_name}")
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