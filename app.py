#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys
from text_detection import get_text, NoTextDetectedException
from config import credentials, DEV
import traceback
import textwrap
import re
from datetime import datetime
import os
import time
import base64
import atexit
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    WebDriverException, StaleElementReferenceException,
    ElementNotInteractableException)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from pyvirtualdisplay.smartdisplay import SmartDisplay

logging.basicConfig(level=logging.DEBUG)

for lib in ["selenium", "botocore", "urllib3", "PIL", "s3transfer"]:
    logging.getLogger(lib).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

valid_accounts = {c[0]: c for c in credentials}  # Set of account names

# e.g. '13:00 - 19:00 Arası - [29]'
time_regex = re.compile(
    r"^(\d\d):\d\d - \d\d:\d\d(?::\d\d)? Arası (?:- )?\[(.*)]$")
seat_regex = re.compile(r'M-\d+ / S-(\d+)')
reservation_regex = re.compile(
    r"^(\d\d\.\d\d\.\d\d\d\d) - (\d\d):\d\d:\d\d - \d\d:\d\d:\d\d$")

DESIRED_TIMES = ['11', '13', '17', '19']
DESIRED_SEATS = [
    [ 148, 154, 142 ],
    [
        133, 135, 136, 138, 139, 141, 142, 144,
        145, 147, 148, 150, 151, 153, 154, 156,
    ],
    [ 74, 81, 88, 95 ],
    [
        67, 69, 70, 72, 76, 77, 79,
        83, 84, 86, 90, 91, 93,
        97, 98, 100, 102, 104, 105, 107,
        109, 111, 112, 114, 116, 118, 119, 121,
    ],
]


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

    def is_past(self, hour: str):
        """Return True if the date with specified time is in the past"""
        return self._date.replace(hour=int(hour)) < datetime.now()


class Driver(webdriver.Chrome):
    LOGIN_URL = "https://kutuphane.uskudar.bel.tr/yordam/?p=2&dil=0&yazilim=yordam&devam=2f796f7264616d2f3f703d372664696c3d30"

    def __init__(self, name, username, password):
        self.account_name = name
        self.username = username
        self.password = password
        options = Options()
        options.add_argument(f'--log-path={os.devnull}')
        super().__init__(options=options)

    def login(self, close_panel=True):
        self.get(self.LOGIN_URL)

        captcha_text = self.extract_captcha_text()

        username_field = self.find_element(By.CSS_SELECTOR, '[name="uyeKodKN"]')
        password_field = self.find_element(By.CSS_SELECTOR, '[name="aSifre"]')
        captcha_field = self.find_element(By.CSS_SELECTOR, '[name="code_girisForm"]')

        username_field.send_keys(self.username)
        password_field.send_keys(self.password)
        captcha_field.send_keys(captcha_text)

        btn = self.find_element(By.CSS_SELECTOR, '[type="submit"]')
        btn.click()

        self.wait_for((By.CLASS_NAME, Dropdown.LIBRARY))
        if close_panel:
            self.wait_for_and_click((By.CLASS_NAME, "gosterme"))

        return self

    def save_captcha(self, ele_captcha, save_loc):
        img_captcha_base64 = self.execute_async_script("""
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

    def extract_captcha_text(self):
        captcha_img = self.find_element(By.CSS_SELECTOR, 'img.captcha')
        loc = "raw_captcha.jpeg"
        self.save_captcha(captcha_img, loc)
        return get_text(loc)

    def wait_for(self, element):
        WebDriverWait(self, 10).until(EC.presence_of_element_located(element))

    def wait_for_and_click(self, element):
        time.sleep(5)
        self.find_element(*element).click()
        # TODO: WebDriverWait(self, 10).until(EC.element_to_be_clickable(element))

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

    def get_date_dropdown(self):
        return self.get_dropdown(Dropdown.DATE)

    def get_time_dropdown(self):
        return self.get_dropdown(Dropdown.TIME)

    def has_reservation(self) -> bool:
        return len(self.find_elements(By.CSS_SELECTOR, "div.toast-body>p")) != 0

    def get_available_seats(self): # -> dict[int, WebElement]
        logger.debug(f"getting available seats...")
        time.sleep(4) # more than 1, less than 5
        available_seats_selector = "span.sandalye.musait"
        seat_elements = self.find_elements(
            By.CSS_SELECTOR, available_seats_selector)
        seats = {}
        for el in seat_elements:
            title = el.get_attribute("title") # M-37 / S-165
            num = int(seat_regex.match(title).groups()[0])
            el.num = num
            seats[num] = el
        return seats

    def get_time_options(self): # -> dict[str, tuple[str, int]]
        """
        e.g. {
            '00': ('00:00 - 06:00 Arası - [184]', 0),
            '07': ('07:00 - 13:00 Arası - [164]', 19),
            '13': ('13:00 - 19:00 Arası - [29]', 0),
            '19': ('19:00 - 23:59:59 Arası - [148]', 0),
        }
        """
        time_options = {}
        for o in self.get_time_dropdown().options:
            try:
                hour, count = time_regex.match(o.text).groups()
            except Exception:
                logger.info(f"{o.text = }")
            if count == 'Dolu':
                count = 0
            time_options[hour] = (o.text, int(count))
        return time_options

    def get_available_weekdays(self): # -> list[Date]
        date_dropdown = self.get_date_dropdown()
        available_dates = [] # : list[Date]
        available_weekdays = [] # : list[Date]
        for option in date_dropdown.options:
            date = Date(option.text)
            available_dates.append(date)
            if date.is_weekday():
                available_weekdays.append(date)
        logger.info(f'{available_dates = }')
        return available_weekdays

    def select_date(self, date):
        self.get_date_dropdown().select_by_visible_text(date.text)
        logger.info(f'selected date {date}')
        time.sleep(1)

    def select_time(self, hour):
        """
        arg time (str): '13'
        """
        time_options = self.get_time_options()
        if hour not in time_options:
            logger.info(f"hour {hour} not in options {time_options}")
            return False
        time_text, count = time_options[hour]
        if count == 0:
            logger.info(f"hour {hour} is full")
            return False
        try:
            self.get_time_dropdown().select_by_visible_text(time_text)
        except NoSuchElementException:
            logger.error(f"invalid time {time_text}")
            logger.error(f"valid times: {self.get_time_options()}")
            logger.error(f"couldn't reserve")
            traceback.print_exc()
            return False
        logger.info(f'selected time {time_text!r}')
        time.sleep(1)
        return True

    def reserve_seat(self, seat: WebElement):
        seat.click()
        time.sleep(1)
        self.click_yes()

    def reserve_for_date(self, date: Date, already_reserved):
        """Reserves for next unreserved desired time slot on given date"""
        self.select_date(date)
        seat = None
        for hour in DESIRED_TIMES:
            if date.is_past(hour):
                logger.info(f"{(date.text, hour)} has passed")
                continue
            if (date.text, hour) in already_reserved:
                logger.info(f"{(date.text, hour)} already reserved")
                continue
            if not self.select_time(hour):
                continue
            seat = self.find_a_seat()
            if seat is None:
                logger.info(f"no seats found for hour {hour}")
                continue
            logger.info(f"found seat #{seat.num}")
            break

        if seat is None:
            raise AllSeatsOccupiedException()

        self.reserve_seat(seat)

    def reserve_for_date_and_hour(self, date, hour):
        self.select_date(date)

        logger.debug(f"{hour = }")
        if m := re.fullmatch(r'^(\d\d)(:00)?$', hour):
            hour = m.groups()[0]
            logger.debug(f"reformatted {hour = }")
        else:
            logger.error(f"invalid hour format: {hour}")
            logger.error(f"use one of following formats: ['13', '13:00']")

        if not self.select_time(hour):
            raise AllSeatsOccupiedException()

        if (seat := self.find_a_seat()) is None:
            raise AllSeatsOccupiedException()
        logger.debug(f"{seat = }, {seat.num = }")

        self.reserve_seat(seat)

    def find_a_seat(self): # -> WebElement | None
        available_seats = self.get_available_seats()
        logger.debug(f"available_seats = {available_seats.keys()}")

        for tier in DESIRED_SEATS:
            for num in tier:
                if num in available_seats:
                    return available_seats[num]

        return None

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


def extract_args(args, label, n_args=1):
    """
    res:
        one value if n_args is 1
        list of values if n_args is > 1
    """
    if n_args < 1:
        raise ValueError("n_args must be >= 1")

    index = args.index(label)
    try:
        res = args[index+1:index+1+n_args]
    except ValueError:
        logger.error(f"invalid number of arguments for {label!r}\n{args = }")
        raise

    if n_args == 1:
        res = res[0]

    return res


def get_credentials(name):
    if creds := valid_accounts.get(name):
         logger.info(f"{creds = }")
    else:
        logger.error(
            "please provide a valid account name\n"
            f"valid account names are: {valid_accounts.keys()}")
        raise ValueError()
    return creds


def get_reservation_details(args):
    index = args.index('--reserve')
    try:
        account, date, time_text = extract_args(args, '--reserve', n_args=3)
    except ValueError:
        logger.error(
            "please provide an account name, date, and time for reservation\n"
            "example: '--reserve Gihad 04.11.2022 19:00'")
        raise

    if account not in valid_accounts:
        logger.info(f"{account = }")
        logger.error(
            "please provide a valid account name\n"
            f"valid account names are: {valid_accounts}")
        raise ValueError()

    # TODO: check format of date

    return account, date, time_text
# --------


def check_reservations():
    global driver

    already_reserved = set()
    accounts = []
    for account in credentials:
        name, username, password = account

        driver = Driver(name, username, password).login(close_panel=False)
        driver.select_haluk_dursun()

        if not driver.has_reservation():
            logger.info(f"no reservation currently exists for {name}")
            accounts.append(account)
            driver.close()
            continue

        logger.info(f'reservation already exists for {driver.account_name}')
        text = driver.find_element(By.CSS_SELECTOR, "div.toast-body>p").text
        try:
            _, seat, date_hour = text.split('\n')
        except ValueError:
            logger.debug(f"{text = }")
            logger.error(f"couldn't extract reservation details")
            driver.close()
            continue
        seat_num = seat_regex.match(seat).groups()[0]
        date, hour = reservation_regex.match(date_hour).groups()
        logger.info(f"reservation: {seat_num = }, {date = }, {hour = }")
        already_reserved.add((date, hour))  # e.g. ('02.11.2022', '19'),
        driver.close()

    return accounts, already_reserved


def reserve_all(accounts, already_reserved):
    global driver

    for account in accounts:
        name, username, password = account
        logger.info(f"reserving for {name}...")

        driver = Driver(name, username, password).login()
        driver.select_haluk_dursun()

        # wait for page load
        time.sleep(5)

        available_weekdays = driver.get_available_weekdays() # list[Date]

        if len(available_weekdays) == 0:
            logger.info(f'no available weekdays found')
            driver.close()
            return

        for date in available_weekdays:
            try:
                driver.reserve_for_date(date, already_reserved)
                break
            except AllSeatsOccupiedException:
                logger.info(f'desired seats are all occupied for date {date}')
                continue
        else:
            logger.info(f"all days are full")
            driver.close()
            return

        # wait for success message
        time.sleep(3)

        driver.close()


def main():
    global driver

    args = sys.argv[1:]

    help_text = textwrap.dedent("""
        valid arguments:
            --help
            --check
            --login-only
            --reserve-all
            --reserve Gihad 04.11.2022 19:00
    """)

    if '--help' in args:
        print(help_text)
    elif '--check' in args:
        # check all reservations
        accounts, already_reserved = check_reservations()
        logger.info(f"{accounts = }")
        logger.info(f"{already_reserved = }")
    elif '--login-only' in args:
        name = extract_args(args, '--login-only')
        logger.info(f"{name = }")
        creds = get_credentials(name)
        driver = Driver(*creds).login(close_panel=False)
        driver.select_haluk_dursun()
        # urllib3.exceptions.MaxRetryError:
    elif '--reserve-all' in args:
        accounts, already_reserved = check_reservations()
        logger.info(f"{accounts = }")
        logger.info(f"{already_reserved = }")
        reserve_all(accounts, already_reserved)
    elif '--reserve' in args:
        name, date_text, hour = get_reservation_details(args)
        logger.debug(f"{date_text = }")
        date = Date(date_text)
        logger.debug(f"{date = }")
        creds = get_credentials(name)
        driver = Driver(*creds).login()
        driver.select_haluk_dursun()
        if driver.has_reservation():
            logger.info(f"reservation already exists for {name}")
            driver.close()
            return
        try:
            driver.reserve_for_date_and_hour(date, hour)
        except AllSeatsOccupiedException:
            logger.error(f"all seats occupied")
        driver.close()

    else:
        if len(args) == 1:
            logger.error(f"invalid argument: {args[0]}")
        else:
            logger.error(f"invalid arguments: {args}")
        print(help_text)


if __name__ == '__main__':
    disp = None
    if not DEV:
        disp = SmartDisplay()
        disp.start()
    main()
    if disp:
        disp.stop()
