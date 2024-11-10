import os
import sys

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

CHROMEDRIVER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "driver",
    "chromedriver",
)

sys.path.insert(0, CHROMEDRIVER_PATH)


class Selenium:

    def __init__(self, url: str):
        self.url = url
        self.driver = None
        self._create_driver()

    def _create_driver(self):
        service = Service(executable_path=CHROMEDRIVER_PATH)
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(service=service, options=options)

    def get_html_content(self) -> str:
        try:
            self.driver.get(self.url)
            rendered_html = self.driver.page_source
        except WebDriverException as e:
            print(f"Error fetching URL {self.url}: {e}")
            rendered_html = ""
        finally:
            self.driver.quit()
        return rendered_html
