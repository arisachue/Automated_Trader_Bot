#!/usr/bin/env python3
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py --test prod-like; sleep 1; done

import argparse
from collections import deque
from enum import Enum
import time
import socket
import random
import json

# ~~~~~============== CONFIGURATION  ==============~~~~~
# Replace "REPLACEME" with your team name!
team_name = "MAGNEMITE"

class Offer:
    def __init__(self, bid, ask):
        self.bid = bid
        self.ask = ask

# ~~~~~============== MAIN LOOP ==============~~~~~

positions = {
    "GS" : 0,
    "MS" : 0,
    "WFC" : 0,
    "XLF" : 0,
    "VALE" : 0,
    "VALBZ" : 0,
    "BOND" : 0
}

estimated_fair = {
    "GS" : -1,
    "MS" : -1,
    "WFC" : -1,
    "XLF" : -1,
    "VALE": -1,
    "VALBZ" : -1,
    "BOND" : 1000,
}

INF = 100000000000
best_offer = {
    "GS" : Offer(-INF, INF),
    "MS" : Offer(-INF, INF),
    "WFC" : Offer(-INF, INF),
    "XLF" : Offer(-INF, INF),
    "VALE" : Offer(-INF, INF),
    "VALBZ" : Offer(-INF, INF),
    "BOND" : Offer(-INF, INF)
}

def best_price_size(message, side):
    if message[side]:
        if len(message[side]) > 0:
            return message[side][0][0], message[side][0][1]

    #TODO: handle empty book
    if side == "buy":
        return -1000000000000000, -1
    if side == "sell":
        return 1000000000000000, -1

    assert False


cur_order_id = 1

def take_bonds(message, exchange):
    global cur_order_id
    bid_prices = message["buy"]
    ask_prices = message["sell"]

    for bid in bid_prices:
        (price, vol) = bid
        if price < 1000:
            break

        exchange.send_add_message(order_id=cur_order_id, symbol="BOND", dir=Dir.SELL, price=price, size=vol)
        cur_order_id += 1

    for ask in ask_prices:
        (price, vol) = ask
        if price >= 1000:
            break

        exchange.send_add_message(order_id=cur_order_id, symbol="BOND", dir=Dir.BUY, price=price, size=vol)
        cur_order_id += 1

def penny_bonds(message, exchange):
    global cur_order_id
    bid_prices = message["buy"]
    ask_prices = message["sell"]

    best_bid, bid_vol = best_price_size(message, "buy")
    best_ask, ask_vol = best_price_size(message, "sell")

    eps = 1
    width = best_ask - best_bid

    our_bid_vol = 5
    our_ask_vol = 5
    

    if width < 3: # fix magic numbers/?? 
        return

    # how many to buy?
    if best_bid <= 1000000 and positions["BOND"] + our_bid_vol <= 100:
        exchange.send_add_message(order_id=cur_order_id, symbol="BOND", dir=Dir.BUY, price=best_bid+eps, size=our_bid_vol)
        cur_order_id += 1

    if best_ask <= 1000000 and positions["BOND"] - our_ask_vol >= -100:
        exchange.send_add_message(order_id=cur_order_id, symbol="BOND", dir=Dir.SELL, price=best_ask-eps, size=our_ask_vol) 
        cur_order_id += 1


def update_position(message):
    global positions
    if message["dir"] == Dir.BUY:
        positions[message["symbol"]] += message["size"]
    if message["dir"] == Dir.SELL:
        positions[message["symbol"]] -= message["size"] 


def handle_bonds(message, exchange):
    take_bonds(message, exchange)
    penny_bonds(message, exchange)

def handle_valbz(message, exchange):
    global cur_order_id
    global best_offer
    valbz_bids = message["buy"]
    valbz_asks = message["sell"]

    best_bid, bid_vol = best_price_size(message, "buy")
    best_ask, ask_vol = best_price_size(message, "sell")

    if estimated_fair["VALBZ"] < 0:
        estimated_fair["VALBZ"] = (best_bid + best_ask) // 2

    best_offer["VALBZ"] = Offer(best_bid, best_ask)

    best_vale_bid = best_offer["VALE"].bid
    best_vale_ask = best_offer["VALE"].ask

    if best_bid > best_vale_ask: # vale and valbz disjoint
        # buy vale, sell valbz
        order_size = min(10 - positions["VALE"], positions["VALBZ"] + 10)
        order_size = 2 
        if positions["VALE"] < 10 and positions["VALBZ"] > -10:
            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.BUY, price=best_vale_ask, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.SELL, price=best_bid, size=order_size)
            cur_order_id += 1
    elif best_vale_bid > best_ask:
        order_size = min(10 + positions["VALE"], 10 - positions["VALBZ"])
        order_size = 2 
        if positions["VALE"] > -10 and positions["VALBZ"] < 10:
            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.SELL, price=best_vale_bid, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.BUY, price=best_ask, size=order_size)
            cur_order_id += 1
    else:
        dif_right = best_vale_ask - best_ask
        dif_left =  best_bid - best_vale_bid
        eps = 1 # 2?

        if dif_right > dif_left and dif_right > eps + 1 and abs(positions["VALE"]) + 2 <= 10 and abs(positions["VALBZ"])+2 <= 10: # buying vale, selling valbz
            order_size = min(10 + positions["VALE"], 10 - positions["VALBZ"])
            order_size = 2 
            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.SELL, price=best_vale_bid-eps, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.BUY, price=best_ask, size=order_size)
            cur_order_id += 1
        elif dif_right < dif_left and dif_left > eps + 1 and abs(positions["VALE"]) + 2 <= 10 and abs(positions["VALBZ"])+2 <= 10: # buying valbz, selling vale
            order_size = min(10 - positions["VALE"], positions["VALBZ"] + 10)
            order_size = 2 
            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.SELL, price=best_bid-eps, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.BUY, price=best_vale_ask, size=order_size)
            cur_order_id += 1

def handle_vale(message, exchange):
    global cur_order_id
    global best_offer
    vale_bids = message["buy"]
    vale_asks = message["sell"]

    best_bid, bid_vol = best_price_size(message, "buy")
    best_ask, ask_vol = best_price_size(message, "sell")

    if estimated_fair["VALE"] < 0:
        estimated_fair["VALE"] = (best_bid + best_ask) // 2

    best_offer["VALE"] = Offer(best_bid, best_ask)

    best_valbz_bid = best_offer["VALBZ"].bid
    best_valbz_ask = best_offer["VALBZ"].ask

    if best_valbz_bid > best_ask: # vale and valbz disjoint
        # buy vale, sell valbz
        order_size = min(10 - positions["VALE"], positions["VALBZ"] + 10)
        order_size = 2 
        if positions["VALE"]+2 < 10 and positions["VALBZ"]-2 > -10:
            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.BUY, price=best_ask, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.SELL, price=best_valbz_bid, size=order_size)
            cur_order_id += 1
    elif best_bid > best_valbz_ask:
        order_size = min(10 + positions["VALE"], 10 - positions["VALBZ"])
        order_size = 2 
        if positions["VALE"]-2 > -10 and positions["VALBZ"]+2 < 10:
            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.SELL, price=best_bid, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.BUY, price=best_valbz_ask, size=order_size)
            cur_order_id += 1
    else:
        dif_right = best_ask - best_valbz_ask
        dif_left =  best_valbz_bid - best_bid
        eps = 1 # 2?

        if dif_right > dif_left and dif_right > eps + 1 and abs(positions["VALE"]) + 2 <= 10 and abs(positions["VALBZ"]) +2 <= 10: # buying vale, selling valbz
            order_size = min(10 + positions["VALE"], 10 - positions["VALBZ"])
            order_size = 2 
            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.SELL, price=best_bid-eps, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.BUY, price=best_valbz_ask, size=order_size)
            cur_order_id += 1
        if dif_right < dif_left and dif_left > eps + 1 and abs(positions["VALE"]) + 2 <= 10 and abs(positions["VALBZ"])+2 <= 10: # buying valbz, selling vale
            order_size = min(10 - positions["VALE"], positions["VALBZ"] + 10)
            order_size = 2 
            exchange.send_add_message(order_id=cur_order_id, symbol="VALBZ", dir=Dir.SELL, price=best_valbz_bid-eps, size=order_size)
            cur_order_id += 1

            exchange.send_add_message(order_id=cur_order_id, symbol="VALE", dir=Dir.BUY, price=best_ask, size=order_size)
            cur_order_id += 1

def handle_stocks(message, exchange):
    global cur_order_id
    best_bid, _ = best_price_size(message, "buy")
    best_ask, _ = best_price_size(message, "sell")
    best_offer[message["symbol"]] = Offer(best_bid, best_ask)

    if 3000 + 2 * best_offer["GS"].bid + 3 * best_offer["MS"].bid + 2 * best_offer["WFC"].bid > 10 * best_offer["XLF"].ask and positions["XLF"] + 3 <= 100 and random.randint(0,1) == 0:
        exchange.send_add_message(order_id=cur_order_id, symbol="XLF", dir=Dir.BUY, price=best_offer["XLF"].ask, size=3)
        cur_order_id += 1

        exchange.send_add_message(order_id=cur_order_id, symbol="GS", dir=Dir.SELL, price=best_offer["GS"].ask, size=3)
        cur_order_id += 1
        exchange.send_add_message(order_id=cur_order_id, symbol="MS", dir=Dir.SELL, price=best_offer["MS"].ask, size=3)
        cur_order_id += 1
        exchange.send_add_message(order_id=cur_order_id, symbol="WFC", dir=Dir.SELL, price=best_offer["WFC"].ask, size=3)
        cur_order_id += 1
        exchange.send_add_message(order_id=cur_order_id, symbol="BOND", dir=Dir.SELL, price=best_offer["BOND"].ask, size=3)
        cur_order_id += 1

    if 3000 + 2 * best_offer["GS"].ask + 3 * best_offer["MS"].ask + 2 * best_offer["WFC"].ask > 10 * best_offer["XLF"].bid and positions["XLF"] - 3 >= -100 and random.randint(0,1) == 0:
        exchange.send_add_message(order_id=cur_order_id, symbol="XLF", dir=Dir.SELL, price=best_offer["XLF"].ask, size=3)
        cur_order_id += 1

        exchange.send_add_message(order_id=cur_order_id, symbol="GS", dir=Dir.BUY, price=best_offer["GS"].ask, size=3)
        cur_order_id += 1
        exchange.send_add_message(order_id=cur_order_id, symbol="MS", dir=Dir.BUY, price=best_offer["MS"].ask, size=3)
        cur_order_id += 1
        exchange.send_add_message(order_id=cur_order_id, symbol="WFC", dir=Dir.BUY, price=best_offer["WFC"].ask, size=3)
        cur_order_id += 1
        exchange.send_add_message(order_id=cur_order_id, symbol="BOND", dir=Dir.BUY, price=best_offer["BOND"].ask, size=3)
        cur_order_id += 1

def main():
    args = parse_arguments()

    exchange = ExchangeConnection(args=args)

    # Store and print the "hello" message received from the exchange. This
    # contains useful information about your positions. Normally you start with
    # all positions at zero, but if you reconnect during a round, you might
    # have already bought/sold symbols and have non-zero positions.
    hello_message = exchange.read_message()
    print("First message from exchange:", hello_message)

    vale_bid_price, vale_ask_price = None, None
    vale_last_print_time = time.time()

    # Note: a common mistake people make is to call write_message() at least
    # once for every read_message() response.
    #
    # Every message sent to the exchange generates at least one response
    # message. Sending a message in response to every exchange message will
    # cause a feedback loop where your bot's messages will quickly be
    # rate-limited and ignored. Please, don't do that!
    while True:
        message = exchange.read_message()

        #TODO code position checks

        # Some of the message types below happen infrequently and contain
        # important information to help you understand what your bot is doing,
        # so they are printed in full. We recommend not always printing every
        # message because it can be a lot of information to read. Instead, let
        # your code handle the messages and just print the information
        # important for you!
        if message["type"] == "close":
            print("The round has ended")
            break
        elif message["type"] == "error":
            print(message)
        elif message["type"] == "reject":
            print(message)
        elif message["type"] == "fill":
            update_position(message) # add to other functions
            print(positions)
            print(message)
        elif message["type"] == "book":
            if message["symbol"] == "BOND": # and random.randint(0,1) == 0:
                handle_bonds(message, exchange)
            if message["symbol"] == "GS" and random.randint(0,1) == 0:
              pass
                # handle_stocks(message, exchange)
            if message["symbol"] == "MS" and random.randint(0,1) == 0:
              pass
                # handle_stocks(message, exchange)
            if message["symbol"] == "WFC" and random.randint(0,1) == 0:
              pass
                # handle_stocks(message, exchange)
            if message["symbol"] == "XLF" and random.randint(0,1) == 0:
              pass
                # handle_stocks(message, exchange)
            if message["symbol"] == "VALE":
                continue
                time.sleep(0.005)
                handle_vale(message, exchange)
                vale_bid_price, _ = best_price_size(message, "buy")
                vale_ask_price, _ = best_price_size(message, "sell")

                now = time.time()

                if now > vale_last_print_time + 1:
                    vale_last_print_time = now
                    # print(
                    #     {
                    #         "vale_bid_price": vale_bid_price,
                    #         "vale_ask_price": vale_ask_price,
                    #     }
                    # )
            if message["symbol"] == "VALBZ":
                continue
                time.sleep(0.005)
                handle_valbz(message, exchange)

            # if message["symbol"] == "VALE":
            #     def best_price(side):
            #         if message[side]:
            #             return message[side][0][0]



# ~~~~~============== PROVIDED CODE ==============~~~~~

# You probably don't need to edit anything below this line, but feel free to
# ask if you have any questinos about what it is doing or how it works. If you
# do need to change anything below this line, please feel free to


class Dir(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeConnection:
    def __init__(self, args):
        self.message_timestamps = deque(maxlen=500)
        self.exchange_hostname = args.exchange_hostname
        self.port = args.port
        self.exchange_socket = self._connect(add_socket_timeout=args.add_socket_timeout)

        self._write_message({"type": "hello", "team": team_name.upper()})

    def read_message(self):
        """Read a single message from the exchange"""
        message = json.loads(self.exchange_socket.readline())
        if "dir" in message:
            message["dir"] = Dir(message["dir"])
        return message

    def send_add_message(
        self, order_id: int, symbol: str, dir: Dir, price: int, size: int
    ):
        """Add a new order"""
        self._write_message(
            {
                "type": "add",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "price": price,
                "size": size,
            }
        )

    def send_convert_message(self, order_id: int, symbol: str, dir: Dir, size: int):
        """Convert between related symbols"""
        self._write_message(
            {
                "type": "convert",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "size": size,
            }
        )

    def send_cancel_message(self, order_id: int):
        """Cancel an existing order"""
        self._write_message({"type": "cancel", "order_id": order_id})

    def _connect(self, add_socket_timeout):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if add_socket_timeout:
            # Automatically raise an exception if no data has been recieved for
            # multiple seconds. This should not be enabled on an "empty" test
            # exchange.
            s.settimeout(5)
        s.connect((self.exchange_hostname, self.port))
        return s.makefile("rw", 1)

    def _write_message(self, message):
        json.dump(message, self.exchange_socket)
        self.exchange_socket.write("\n")

        now = time.time()
        self.message_timestamps.append(now)
        if len(
            self.message_timestamps
        ) == self.message_timestamps.maxlen and self.message_timestamps[0] > (now - 1):
            print(
                "WARNING: You are sending messages too frequently. The exchange will start ignoring your messages. Make sure you are not sending a message in response to every exchange message."
            )


def parse_arguments():
    test_exchange_port_offsets = {"prod-like": 0, "slower": 1, "empty": 2}

    parser = argparse.ArgumentParser(description="Trade on an ETC exchange!")
    exchange_address_group = parser.add_mutually_exclusive_group(required=True)
    exchange_address_group.add_argument(
        "--production", action="store_true", help="Connect to the production exchange."
    )
    exchange_address_group.add_argument(
        "--test",
        type=str,
        choices=test_exchange_port_offsets.keys(),
        help="Connect to a test exchange.",
    )

    # Connect to a specific host. This is only intended to be used for debugging.
    exchange_address_group.add_argument(
        "--specific-address", type=str, metavar="HOST:PORT", help=argparse.SUPPRESS
    )

    args = parser.parse_args()
    args.add_socket_timeout = True

    if args.production:
        args.exchange_hostname = "production"
        args.port = 25000
    elif args.test:
        args.exchange_hostname = "test-exch-" + team_name
        args.port = 25000 + test_exchange_port_offsets[args.test]
        if args.test == "empty":
            args.add_socket_timeout = False
    elif args.specific_address:
        args.exchange_hostname, port = args.specific_address.split(":")
        args.port = int(port)

    return args


if __name__ == "__main__":
    # Check that [team_name] has been updated.
    assert (
        team_name != "REPLACEME"
    ), "Please put your team name in the variable [team_name]."

    main()
