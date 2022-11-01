#!/usr/bin/env python
# -*- coding: utf-8 -*-
import boto3
from PIL import Image
import logging


logger = logging.getLogger(__name__)

access_keys = open("library_accessKeys.csv").read().split("\n")[1].split(",")
session = boto3.Session(
    aws_access_key_id=access_keys[0],
    aws_secret_access_key=access_keys[1],
)
rek_client = session.client('rekognition')
s3_client = session.client('s3')

bucket_name = "captchas-1"
bg_name = "bg.png"
img_name = "captcha.png"


class NoTextDetectedException(Exception):
    pass


def get_text(raw_captcha):
    upload_resized(raw_captcha)
    text = get_detected_text()
    return text


def resize(image_loc, save_loc):
    bg = Image.open(bg_name)
    captcha = Image.open(image_loc).convert("RGBA")
    xs = bg.size[0] // 2 - captcha.size[0] // 2
    xe = xs + captcha.size[0]
    ys = bg.size[1] // 2 - captcha.size[1] // 2
    ye = ys + captcha.size[1]
    bg.paste(captcha, box=(xs, ys, xe, ye), mask=captcha)
    bg.save(save_loc, format="png")


def upload_resized(raw_captcha):
    resize(raw_captcha, img_name)
    s3_client.upload_file(img_name, bucket_name, img_name)


def get_detected_text():
    response = rek_client.detect_text(Image={
        'S3Object': {
            'Bucket': bucket_name,
            'Name': img_name,
        }
    })

    text_detections = response['TextDetections']
    if len(text_detections) == 0:
        logger.error('No text detected')
        raise NoTextDetectedException()

    text = text_detections[0]['DetectedText']
    logger.info(f'Detected text: {text!r}')
    return text

