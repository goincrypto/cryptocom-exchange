from .structs import Coin

AAVE = Coin("AAVE")
ADA = Coin("ADA")
ALGO = Coin("ALGO")
ATOM = Coin("ATOM")
BAND = Coin("BAND")
BAT = Coin("BAT")
BCH = Coin("BCH")
BNT = Coin("BNT")
BTC = Coin("BTC")
CELR = Coin("CELR")
COMP = Coin("COMP")
CRO = Coin("CRO")
CRV = Coin("CRV")
DAI = Coin("DAI")
DOT = Coin("DOT")
EGLD = Coin("EGLD")
ENJ = Coin("ENJ")
EOS = Coin("EOS")
ETC = Coin("ETC")
ETH = Coin("ETH")
GRT = Coin("GRT")
ICX = Coin("ICX")
KNC = Coin("KNC")
KSM = Coin("KSM")
LINK = Coin("LINK")
LRC = Coin("LRC")
LTC = Coin("LTC")
MANA = Coin("MANA")
MCO = Coin("MCO")
MKR = Coin("MKR")
NEO = Coin("NEO")
OMG = Coin("OMG")
ONT = Coin("ONT")
PAXG = Coin("PAXG")
QTUM = Coin("QTUM")
REN = Coin("REN")
SKL = Coin("SKL")
UNI = Coin("UNI")
USDC = Coin("USDC")
USDT = Coin("USDT")
VET = Coin("VET")
WBTC = Coin("WBTC")
XLM = Coin("XLM")
XRP = Coin("XRP")
XTZ = Coin("XTZ")
YFI = Coin("YFI")
ZIL = Coin("ZIL")


def all():
    return [
        value for name, value in globals().items()
        if isinstance(value, Coin)
    ]
