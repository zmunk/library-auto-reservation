import logging
import sys
from text_detection import get_text, NoTextDetectedException
from config import username, password

import re
from datetime import datetime
import os
import time
import base64
import atexit
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (WebDriverException, StaleElementReferenceException)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

raw_captcha = "raw_captcha.jpeg"

def save_captcha(driver, ele_captcha, save_loc):
    img_captcha_base64 = driver.execute_async_script("""
        var ele = arguments[0], callback = arguments[1];
        ele.addEventListener('load', function fn(){
        ele.removeEventListener('load', fn, false);
        var cnv = document.createElement('canvas');
        cnv.width = this.width; cnv.height = this.height;
        cnv.getContext('2d').drawImage(this, 0, 0);
        callback(cnv.toDataURL('image/jpeg').substring(22));
        }, false);
        ele.dispatchEvent(new Event('load'));
        """, ele_captcha)
    with open(save_loc, 'wb') as f:
        f.write(base64.b64decode(img_captcha_base64))


class Dropdown:
    LIBRARY = "kutuphaneSec"
    DATE = "tarihSec"
    TIME = "saatSec"


class Date:
    FORMAT = '%d.%m.%Y'  # e.g. '01.11.2022'

    def __init__(self, date):
        self._date = datetime.strptime(date, self.FORMAT)

    def __str__(self):
        return datetime.strftime(self._date, self.FORMAT)

    def is_weekday(self) -> bool:
        return self._date.weekday() < 5


class Driver(webdriver.Firefox):
    LOGIN_URL = "https://kutuphane.uskudar.bel.tr/yordam/?p=2&dil=0&yazilim=yordam&devam=2f796f7264616d2f3f703d372664696c3d30"

    def __init__(self):
        options = Options()
        options.add_argument(f'--log-path={os.devnull}')
        super().__init__(options=options)

    def login(self):
        self.get(self.LOGIN_URL)
        captcha_img = driver.find_element(By.CSS_SELECTOR, 'img.captcha')
        save_captcha(self, captcha_img, raw_captcha)

        captcha_text = get_text(raw_captcha)

        username_field = self.find_element(By.CSS_SELECTOR, '[name="uyeKodKN"]')
        password_field = self.find_element(By.CSS_SELECTOR, '[name="aSifre"]')
        captcha_field = self.find_element(By.CSS_SELECTOR, '[name="code_girisForm"]')

        username_field.send_keys(username)
        password_field.send_keys(password)
        captcha_field.send_keys(captcha_text)

        btn = self.find_element(By.CSS_SELECTOR, '[type="submit"]')
        btn.click()

    def wait_for(self, element):
        WebDriverWait(self, 10).until(EC.presence_of_element_located(element))

    def get_dropdown(self, dropdown_name):
        return Select(self.find_element(By.CLASS_NAME, dropdown_name))

    def get_available_seats(self):
        available_seats_selector = "span.sandalye.musait"
        seat_elements = self.find_elements(
            By.CSS_SELECTOR, available_seats_selector)
        pattern = re.compile(r'M-\d+ / S-(\d+)')
        seats = {}
        for el in seat_elements:
            title = el.get_attribute("title") # M-37 / S-165
            num = int(pattern.match(title).groups()[0])
            seats[num] = el
        return seats


def close_driver():
    try:
        driver.close()
    except (NameError, WebDriverException):
        return

atexit.register(close_driver)

# -- utils
def inspect(obj):
    print(list(filter(lambda x: x[0] != "_", dir(obj))))

if __name__ == '__main__':
    args = sys.argv[1:]

    driver = Driver()
    driver.login()
    driver.wait_for((By.CLASS_NAME, Dropdown.LIBRARY))

    def select(dropdown_name, index):
        dropdown = driver.get_dropdown(dropdown_name)
        while True:
            try:
                Select(dropdown).select_by_index(index)
                return
            except NotImplementedError:
                time.sleep(1)
            except StaleElementReferenceException:
                dropdown = driver.get_dropdown(dropdown_name)

    select(Dropdown.LIBRARY, 1)

    select_date = driver.get_dropdown(Dropdown.DATE)
    for option in select_date.options:
        date = Date(option.text)
        if date.is_weekday():
            logger.info(f'selecting {date}')
            select_date.select_by_visible_text(option.text)
            break
    else:
        logger.error('no weekday found')

    seats = driver.get_available_seats()

    # select(Dropdown.DATE, 1)
    # select(Dropdown.TIME, 1)


    # seats = get_seats()


# if __name__ == '__main__':
    # main()
