#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys
from text_detection import get_text, NoTextDetectedException
from config import credentials, DEV

import re
from datetime import datetime
import os
import time
import base64
import atexit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (WebDriverException, StaleElementReferenceException)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

raw_captcha = "raw_captcha.jpeg"

# e.g. '13:00 - 19:00 Arası - [29]'
time_regex = re.compile(
    r"^(\d\d):\d\d - \d\d:\d\d(?::\d\d)? Arası (?:- )?\[(.*)]$")
seat_regex = re.compile(r'M-\d+ / S-(\d+)')
reservation_regex = re.compile(
    r"^(\d\d\.\d\d\.\d\d\d\d) - (\d\d):\d\d:\d\d - \d\d:\d\d:\d\d$")

DESIRED_TIMES = ['11', '13', '17', '19']
DESIRED_SEATS = [
    [ 148 ],
    [ 74, 81, 88, 95 ],
    [
        67, 69, 70, 72, 76, 77, 79,
        83, 84, 86, 90, 91, 93,
        97, 98, 100, 102, 104, 105, 107,
        109, 111, 112, 114, 116, 118, 119, 121,
        133, 135, 136, 138, 139, 141, 142, 144,
        145, 147, 148, 150, 151, 153, 154, 156,
    ],
]


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


class AllSeatsOccupiedException(Exception):
    pass


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

    @property
    def text(self):
        return str(self)

    def is_weekday(self) -> bool:
        return self._date.weekday() < 5


class Driver(webdriver.Chrome):
    LOGIN_URL = "https://kutuphane.uskudar.bel.tr/yordam/?p=2&dil=0&yazilim=yordam&devam=2f796f7264616d2f3f703d372664696c3d30"

    def __init__(self, name, username, password):
        self.account_name = name
        self.username = username
        self.password = password
        options = Options()
        options.add_argument(f'--log-path={os.devnull}')
        if not DEV:
            options.add_argument('--headless')
        super().__init__(options=options)

    def login(self):
        self.get(self.LOGIN_URL)
        captcha_img = driver.find_element(By.CSS_SELECTOR, 'img.captcha')
        save_captcha(self, captcha_img, raw_captcha)

        captcha_text = get_text(raw_captcha)

        username_field = self.find_element(By.CSS_SELECTOR, '[name="uyeKodKN"]')
        password_field = self.find_element(By.CSS_SELECTOR, '[name="aSifre"]')
        captcha_field = self.find_element(By.CSS_SELECTOR, '[name="code_girisForm"]')

        username_field.send_keys(self.username)
        password_field.send_keys(self.password)
        captcha_field.send_keys(captcha_text)

        btn = self.find_element(By.CSS_SELECTOR, '[type="submit"]')
        btn.click()

    def wait_for(self, element):
        WebDriverWait(self, 10).until(EC.presence_of_element_located(element))

    def select_haluk_dursun(self):
        library_name = 'Haluk Dursun Kütüphanesi'
        dropdown = driver.get_dropdown(Dropdown.LIBRARY)
        for _ in range(10):
            try:
                dropdown.select_by_visible_text(library_name)
                time.sleep(1)
                return
            except Exception:
                time.sleep(0.1)
        logger.error('could not select library')
        raise Exception()

    def get_dropdown(self, dropdown_name):
        while True:
            try:
                return Select(self.find_element(By.CLASS_NAME, dropdown_name))
            except NotImplementedError:
                time.sleep(1)

    def has_reservation(self) -> bool:
        return len(self.find_elements(By.CSS_SELECTOR, "div.toast-body>p")) != 0

    def get_available_seats(self):
        available_seats_selector = "span.sandalye.musait"
        seat_elements = self.find_elements(
            By.CSS_SELECTOR, available_seats_selector)
        seats = {}
        for el in seat_elements:
            title = el.get_attribute("title") # M-37 / S-165
            num = int(seat_regex.match(title).groups()[0])
            seats[num] = el
        return seats

    def get_time_options(self):
        """
        e.g. {
            '00': ('00:00 - 06:00 Arası - [184]', 0),
            '07': ('07:00 - 13:00 Arası - [164]', 19),
            '13': ('13:00 - 19:00 Arası - [29]', 0),
            '19': ('19:00 - 23:59:59 Arası - [148]', 0),
        }
        """
        time_options = {}
        for o in self.get_dropdown(Dropdown.TIME).options:
            try:
                hour, count = time_regex.match(o.text).groups()
            except Exception:
                logger.info(f"{o.text = }")
# '13:00 - 19:00 Arası [Dolu]'
            if count == 'Dolu':
                count = 0
            time_options[hour] = (o.text, int(count))
        return time_options

    def reserve_for_date(self, date, already_reserved):
        self.get_dropdown(Dropdown.DATE).select_by_visible_text(date.text)
        logger.info(f'selected date {date}')
        time.sleep(1)

        # -- select time
        time_dropdown = self.get_dropdown(Dropdown.TIME)
        time_options = self.get_time_options()
        for hour in DESIRED_TIMES:
            if hour not in time_options:
                continue
            if (date.text, hour) in already_reserved:
                logger.info(f"{(date.text, hour)} already reserved")
                continue
            text, count = time_options[hour]
            if count == 0:
                continue
            time_dropdown.select_by_visible_text(text)
            logger.info(f'selected time {hour!r}')
            time.sleep(1)
            break
        else:
            logger.info('all times are full')
            raise AllSeatsOccupiedException()

        seats = self.get_available_seats()

        seat = None
        for tier in DESIRED_SEATS:
            for num in tier:
                if num in seats:
                    seat = seats[num]
                    logger.info(f"reserving seat {num}")
                    break
            if seat:
                break

        if seat is None:
            raise AllSeatsOccupiedException()

        return seat

    def click_yes(self):
        self.find_elements(By.CLASS_NAME, "evet")[-1].click()


def close_driver():
    try:
        driver.close()
    except (NameError, WebDriverException):
        return

atexit.register(close_driver)


# -- utils
def inspect(obj):
    """show properties/methods of obj"""
    print(list(filter(lambda x: x[0] != "_", dir(obj))))


def main():
    global driver, date_dropdown, seats, time_options

    args = sys.argv[1:]

    already_reserved = set()
    accounts = []
    for account in credentials:
        name, username, password = account

        driver = Driver(name, username, password)
        driver.login()
        driver.wait_for((By.CLASS_NAME, Dropdown.LIBRARY))

        driver.select_haluk_dursun()

        if not driver.has_reservation():
            logger.info(f"no reservation currently exists for {name}")
            accounts.append(account)
            driver.close()
            continue

        logger.info(f'reservation already exists for {driver.account_name}')
        text = driver.find_element(By.CSS_SELECTOR, "div.toast-body>p").text
        _, seat, date_hour = text.split('\n')
        seat_num = seat_regex.match(seat).groups()[0]
        date, hour = reservation_regex.match(date_hour).groups()
        logger.info(f"reservation: {seat_num = }, {date = }, {hour = }")
        already_reserved.add((date, hour))  # e.g. ('02.11.2022', '19'),
        driver.close()

    logger.info(f"{already_reserved = }")
    logger.info(f"{accounts = }")

    for account in accounts:
        name, username, password = account
        logger.info(f"reserving for {name}...")

        driver = Driver(name, username, password)
        driver.login()
        driver.wait_for((By.CLASS_NAME, Dropdown.LIBRARY))

        driver.select_haluk_dursun()

        time.sleep(5)  # TODO: replace with wait_for

        date_dropdown = driver.get_dropdown(Dropdown.DATE)

        available_weekdays = []
        for option in date_dropdown.options:
            date = Date(option.text)
            if date.is_weekday():
                available_weekdays.append(date)

        if len(available_weekdays) == 0:
            logger.info(f'no available weekdays found')
            driver.close()
            return

        for date in available_weekdays:
            try:
                seat = driver.reserve_for_date(date, already_reserved)
                break
            except AllSeatsOccupiedException:
                logger.info(f'desired seats are all occupied for date {date}')
                continue
        else:
            logger.info(f"all days are full")
            driver.close()
            return

        seat.click()
        driver.click_yes()

        time.sleep(3)

        driver.close()



if __name__ == '__main__':
    main()
