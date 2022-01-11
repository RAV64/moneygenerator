import json
import os
from datetime import datetime, timedelta
from time import sleep
import concurrent.futures
import numpy as np

from binance.client import Client
from helpers.parameters import load_config
from helpers.handle_creds import load_correct_creds, load_telegram_creds
from helpers.logger import Logger


class FreeMoney:
    def __init__(self):
        self.first_run = True
        self.session_profit_percent = 0
        self.session_profit_amount = 0
        self.data_collected = False
        self.prices = {}
        self.collected_starting_data = False
        self.update_check = False

        parsed_config = load_config('config.yml')
        parsed_creds = load_config('creds.yml')

        ACCESS_KEY, SECRET_KEY = load_correct_creds(parsed_creds)
        TELEGRAM_CHANNEL_ID, TELEGRAM_TOKEN = load_telegram_creds(parsed_creds)

        self.TEST_MODE = parsed_config['script_options']['TEST_MODE']
        self.CUSTOM_LIST = parsed_config['trading_options']['CUSTOM_LIST']
        TELEGRAM_LOGGING = parsed_config['script_options']['TELEGRAM_LOGGING']
        LOG_FILE = parsed_config['script_options']['LOG_FILE']
        TICKERS_LIST = parsed_config['trading_options']['TICKERS_LIST']

        self.DEBUG = parsed_config['script_options']['DEBUG']
        self.PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
        self.QUANTITY = parsed_config['trading_options']['QUANTITY']
        self.MAX_COINS = parsed_config['trading_options']['MAX_COINS']
        self.FIATS = parsed_config['trading_options']['FIATS']
        self.TIME_DIFFERENCE = parsed_config['trading_options']['TIME_DIFFERENCE'] / 60
        self.RECHECK_INTERVAL = parsed_config['trading_options']['RECHECK_INTERVAL']
        self.CHANGE_IN_PRICE = parsed_config['trading_options']['CHANGE_IN_PRICE']
        self.STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
        self.TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
        self.TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
        self.TRAILING_TAKE_PROFIT = parsed_config['trading_options']['TRAILING_TAKE_PROFIT']
        self.SIGNALLING_MODULES = parsed_config['trading_options']['SIGNALLING_MODULES']
        self.TRADING_FEE = parsed_config['trading_options']['TRADING_FEE']

        self.client = Client(ACCESS_KEY, SECRET_KEY)

        self.log = Logger(TELEGRAM_CHANNEL_ID, TELEGRAM_TOKEN,
                          TELEGRAM_LOGGING, LOG_FILE).log

        if not self.TEST_MODE:
            self.coins_bought_file_path = 'files/coins_bought.json'
            print("Using main net! Bot will activate in 10 seconds.")
            sleep(10)
        else:
            self.coins_bought_file_path = 'files/test_coins_bought.json'
            print("Using test net!")

        if os.path.isfile(self.coins_bought_file_path) and os.stat(self.coins_bought_file_path).st_size != 0:
            with open(self.coins_bought_file_path) as file:
                self.coins_bought = json.load(file)
        else:
            self.coins_bought = {}

        if self.CUSTOM_LIST:
            self.tickers = [line.strip()
                            for line in open("files/" + TICKERS_LIST)]

        self.starting_time = datetime.now()
        self.time_tracker = datetime.now()

        while True:
            self.get_prices()

    def get_prices(self):

        if self.first_run:
            coins = self.client.get_all_tickers()
            for coin in coins:
                if any(item + self.PAIR_WITH == coin['symbol'] for item in self.tickers) and all(
                        item not in coin['symbol'] for item in self.FIATS):
                    self.prices[coin['symbol']] = {'price': [float(coin['price'])], 'time': [
                        datetime.now()]}
            self.first_run = False

        if self.time_tracker <= datetime.now() - timedelta(minutes=float(self.TIME_DIFFERENCE / self.RECHECK_INTERVAL)):
            coins = self.client.get_all_tickers()
            self.update_portfolio()
            for coin in coins:
                if any(item + self.PAIR_WITH == coin['symbol'] for item in self.tickers) and all(
                        item not in coin['symbol'] for item in self.FIATS):
                    self.prices[coin['symbol']]['price'].append(
                        float(coin['price']))
                    self.prices[coin['symbol']]['time'].append(
                        datetime.now().timestamp())
                    if self.collected_starting_data:
                        self.prices[coin['symbol']]['price'].pop(0)
                        self.prices[coin['symbol']]['time'].pop(0)

            if not self.collected_starting_data:
                print(len(self.prices['BTCUSDT']['price']),
                      "/", self.RECHECK_INTERVAL, end='\r')
                if len(self.prices['BTCUSDT']['price']) == self.RECHECK_INTERVAL:
                    print("Starting data collected!")
                    self.collected_starting_data = True
            self.time_tracker = datetime.now()
            if self.collected_starting_data:
                self.sell_buy_check()

    def sell(self, coin):

        PriceChange = float(
            (self.prices[coin]['price'][-1] - self.coins_bought[coin]['bought_at']) / self.coins_bought[coin][
                'bought_at'] * 100)
        if not self.TEST_MODE:
            try:
                self.client.create_order(
                    symbol=coin,
                    side='SELL',
                    type='MARKET',
                    quantity=self.coins_bought[coin]['volume']

                )
            except Exception as e:
                print(e)

        profit = ((self.prices[coin]['price'][-1] - self.coins_bought[coin]['bought_at']) *
                  self.coins_bought[coin]['volume']) * (1 - (self.TRADING_FEE * 2))
        self.session_profit_amount += profit
        print(
            f"Session profit: {self.session_profit_amount:.3f} in {datetime.now() - self.starting_time}")
        self.log(
            f"Sell: {self.coins_bought[coin]['volume']} {coin} - {self.coins_bought[coin]['bought_at']} "
            f"{self.prices[coin]['price'][-1]} Profit: {profit:.2f} {PriceChange - (self.TRADING_FEE * 2):.2f}%")

        self.remove_from_portfolio(coin)

    def buy(self, coin):
        volume = self.get_volume(coin)
        order = {}

        if not self.TEST_MODE:
            try:
                self.client.create_order(
                    symbol=coin,
                    side='BUY',
                    type='MARKET',
                    quantity=volume
                )
            except Exception as e:
                print(e)
            else:
                order = self.client.get_all_orders(symbol=coin, limit=1)
                while not order:
                    order = self.client.get_all_orders(symbol=coin, limit=1)
                    sleep(0.5)
        else:
            order = {
                "symbol": coin,
                "orderId": 0,
                "time": datetime.now().timestamp(),
                "price": self.prices[coin]['price'][-1],
                "volume": volume,
                "stop_loss": self.STOP_LOSS,
                "take_profit": self.TAKE_PROFIT,
            }

        self.add_to_portfolio(order, volume)
        self.log(f"Buy: {volume} {coin} - {self.prices[coin]['price'][-1]}")

    def get_volume(self, coin):
        lot_size = {}

        info = self.client.get_symbol_info(coin)
        step_size = info['filters'][2]['stepSize']
        lot_size[coin] = step_size.index('1') - 1

        if lot_size[coin] < 0:
            lot_size[coin] = 0

        volume = float(self.QUANTITY / float(self.prices[coin]['price'][-1]))

        if coin not in lot_size:
            volume = float('{:.1f}'.format(volume))

        else:
            if lot_size[coin] == 0:
                volume = int(volume)
            else:
                volume = float('{:.{}f}'.format(volume, lot_size[coin]))

        return volume

    def sell_buy_check(self):
        coins_to_sell = []
        for coin in self.coins_bought:

            TP = float(self.coins_bought[coin]['bought_at']) + (
                float(self.coins_bought[coin]['bought_at']) * self.coins_bought[coin]['take_profit']) / 100
            SL = float(self.coins_bought[coin]['bought_at']) + (
                float(self.coins_bought[coin]['bought_at']) * self.coins_bought[coin]['stop_loss']) / 100

            LastPrice = float(self.prices[coin]['price'][-1])
            BuyPrice = float(self.coins_bought[coin]['bought_at'])
            PriceChange = float((LastPrice - BuyPrice) / BuyPrice * 100)
            self.coins_bought[coin]['current_price'] = LastPrice
            self.coins_bought[coin]['current'] = PriceChange
            self.coins_bought[coin]['hold_dur'] = datetime.now(
            ).timestamp() - self.coins_bought[coin]['timestamp']

            if LastPrice > TP:

                self.coins_bought[coin]['take_profit'] = PriceChange
                self.coins_bought[coin]['stop_loss'] = (
                    self.coins_bought[coin]['take_profit'] - .15) * .8
                print(
                    f"{coin} TP reached, adjusting TP {self.coins_bought[coin]['take_profit']:.2f} and SL "
                    f"{self.coins_bought[coin]['stop_loss']:.2f}.")
            elif self.prices[coin]['price'][-1] < SL:
                coins_to_sell.append(coin)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for coin in coins_to_sell:
                executor.submit(self.sell, coin)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for coin in self.prices:
                lp = self.prices[coin]['price'][0]  # LAST PRICE
                pc = self.CHANGE_IN_PRICE  # 3%
                mean = np.mean(self.prices[coin]['price'][1:])
                last_price_plus_change = lp + (lp * pc) / 100
                if last_price_plus_change < mean and coin not in self.coins_bought:
                    executor.submit(self.buy, coin)
                else:
                    pass

    def add_to_portfolio(self, order, volume):
        self.coins_bought[order['symbol']] = {
            'symbol': order['symbol'],
            'order_id': order['orderId'],
            'timestamp': order['time'],
            'bought_at': order['price'],
            'current_price': order['price'],
            'hold_dur': 0,
            'volume': volume,
            'stop_loss': -self.STOP_LOSS,
            'take_profit': self.TAKE_PROFIT,
            'current': 0
        }
        with open(self.coins_bought_file_path, 'w') as file:
            json.dump(self.coins_bought, file, indent=4)

    def remove_from_portfolio(self, coin):
        self.coins_bought.pop(coin)

        with open(self.coins_bought_file_path, 'w') as file:
            json.dump(self.coins_bought, file, indent=4)

    def update_portfolio(self):
        with open(self.coins_bought_file_path, 'w') as file:
            json.dump(self.coins_bought, file, indent=4)


if __name__ == '__main__':
    FreeMoney()
