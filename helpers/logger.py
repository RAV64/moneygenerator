from datetime import datetime

import requests


class Logger:
    def __init__(self, telegram_channel_id, telegram_token, telegram_logging, log_file):
        self.TELEGRAM_CHANNEL_ID = telegram_channel_id
        self.TELEGRAM_TOKEN = telegram_token
        self.TELEGRAM_LOGGING = telegram_logging
        self.LOG_FILE = log_file

    def log(self, content):
        timestamp = datetime.now().strftime("%d/%m %H:%M:%S")
        print(f"[{timestamp}]: {content}")
        with open("files/" + self.LOG_FILE, 'a+') as f:
            f.write(timestamp + ' ' + content + '\n')

        #logging.basicConfig(filename="files/" + self.LOG_FILE, encoding='utf-8', format='[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S')
        # logging.info(content)

        if self.TELEGRAM_LOGGING:
            payload = {
                'chat_id': self.TELEGRAM_CHANNEL_ID,
                'text': content,
                'parse_mode': 'HTML'
            }
            return requests.post(f"https://api.telegram.org/bot{self.TELEGRAM_TOKEN}/sendMessage",
                                 data=payload).content
