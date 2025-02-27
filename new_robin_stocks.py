#!/usr/bin/python3
import time
import robin_stocks2 as robin_stocks
import configparser
import json
import requests
import os
from barchart import Barchart
from new_finviz import FinViz
from work_sql import Track_Buys
from figure_std import Find_SLP

b = Barchart()

config = configparser.ConfigParser()

fv_symbols = FinViz().full

def is_market_open():
    end = 'https://financialmodelingprep.com/api/v3/is-the-market-open?apikey=07d01d0e9e3d5d7aef46d93a6a0c4529'
    data = json.loads(requests.get(end))
    return data['isTheStockMarketOpen']

def prompt_creds():
  if os.path.isfile('/home/ec2-user/.saver.cfg'):
    os.remove('/home/ec2-user/.saver.cfg')
  username = input ("Enter RobinHood username: ")
  password = input ("Enter RobinHood password: ")
  config.add_section('ROBINHOOD')
  config['ROBINHOOD']['username'] = username
  config['ROBINHOOD']['password'] = password
  with open('/home/ec2-user/.saver.cfg', 'w') as configfile:
    config.write(configfile)

def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

def get_creds():
  if os.path.isfile('/home/ec2-user/.saver.cfg') is False:
    prompt_creds()
  data = config.read('/home/ec2-user/.saver.cfg')
  if config.has_section('ROBINHOOD') is False:
    prompt_creds()
  if config.has_option('ROBINHOOD', 'username') is False:
    prompt_creds()
  if config.has_option('ROBINHOOD', 'password') is False:
    prompt_creds()
  username = config['ROBINHOOD']['username']
  password = config['ROBINHOOD']['password']
  return username, password

def get_rh_rating(symbol, analyst):
    data = robin_stocks.stocks.get_ratings(symbol, info=None)
    if isinstance(data, str) is True:
        data = data.rstrip('\n')
        if len(data) == 0:
            return None
    if data is None:
        return None
    if data['summary'] is None:
        return None
    buy = data['summary']['num_buy_ratings']
    if buy < analyst:
        return None
    hold = data['summary']['num_hold_ratings']
    sell = data['summary']['num_sell_ratings']
    total = buy + hold + sell
    per = buy / total * 100
    if per > 90:
        return True

def get_cp(symbol):
    data = robin_stocks.stocks.get_quotes(symbol)[0]['last_trade_price']
    return float(data)
    
if is_market_open() is False:
    print("The market is closed")
    exit()

username, password = get_creds()
robin_stocks.login(username, password)
cash = float(robin_stocks.profiles.load_account_profile()['portfolio_cash'])
symbol = 'GLUU'
cp = get_cp(symbol)
slp = Find_SLP().get_slp(symbol)
new_slp = cp * slp
lp = cp * 1.01
if cash < lp:
    print("I don't have enough cash")
    exit()
quantity = int(100 / cp)
quantity = 1
print("buying %s, quantity = %i, limit price = %f" % ( symbol, quantity,lp))
buy_data = robin_stocks.orders.order_buy_limit(symbol, quantity,lp,timeInForce='gtc', extendedHours=True)
print(buy_data)
order = buy_data['id']
while buy_data['state'] != 'filled': 
    time.sleep(5)
    buy_data = robin_stocks.orders.get_stock_order_info(order)
exit()

buys = []
bought_symbols = Track_Buys().get_symbols()

d = FinViz().full()
for symbol in d:
    if get_rh_rating(symbol, 10) is True and b.buy(symbol) is True:
        buys.append(symbol)

def buy(symbol):
    cp = get_cp(symbol)
    limitprice = cp * 1.0025
    quantity = int(100 / cp)
    if quantity == 0:
        quantity = 1
    cash = float(robin_stocks.profiles.load_account_profile()['portfolio_cash'])
    if cash < limitprice:
        return False
    if cash < limitprice * quantity:
        quantity = 1
    buy_data = robin_stocks.orders.order_buy_limit(symbol, quantity,limitprice,timeInForce='gtc', extendedHours=False)
    order = buy_data['id']
    while buy_data['state'] == 'queued':
        time.sleep('5')
        buy_data = robin_stocks.orders.get_stock_order_info(order)
    if buy_data['state'] == 'filled':
        return True
    return False

for symbol in buys:
    print(symbol)
    cp = get_cp(symbol)
    slp = Find_SLP().get_slp(symbol)
    new_slp = cp * slp
    lp = cp * 1.25
    Track_Buys().buy(symbol, cp, True)
    if symbol not in bought_symbols:
        print("buying %s, quantity = %i, limit price = %f" % ( symbol, quantity,lp))
        buy_data = robin_stocks.orders.order_buy_limit(symbol, quantity,lp,timeInForce='gtc', extendedHours=True)
        buy_data = robin_stocks.orders.order_buy_market(symbol, quantity, timeInForce='gtc', priceType='ask_price', extendedHours=False)
        order = buy_data['id']
        while buy_data['state'] != 'filled' or buy_data['state'] != 'canceled':
            buy_data = robin_stocks.orders.get_stock_order_info(order)
            time.sleep('5')

for symbol in bought_symbols:
    if symbol not in buys:
        cp = get_cp(symbol)
        slp = Find_SLP().get_slp(symbol)
        new_slp = cp * slp
        quanity =  int(100 / cp)
        print("The current price is %f and the slp should be %f below that, setting slp at %f" % ( cp , slp, new_slp))
        Track_Buys().update_price(symbol, cp, False)
