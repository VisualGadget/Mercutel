# Edit this file and rename it to config.py

WDT_ENABLE = False  # Watchdog timer

# last 6 digits of electric meter serial number, not including:
# - year of manufacture (two last digits after dash or space)
# - leading zeroes
ECOUNTER_NETWORK_ADDRESS = 123456

# GMT TIMEZONE for clock synchronization
TIMEZONE = +5

# MQTT broker
MQTT_SERVER = '192.168.1.100'
MQTT_USER = 'MQTT_USER_NAME'
MQTT_PASSWORD = 'MQTT_PASSWORD'

# GPIO of ESP8266
PIN_TXE = 12  # transceiver/receiver control
PIN_RX = 13  # using UART0 pin swap on ESP8266
PIN_TX = 15  #

# TRIC energy reporting service (https://itpc.ru)
TRIC_ACCOUNT = '1234567'  # account number
TRIC_PASSWORD = 'ACCOUNT_PASSWORD'  # account password
# aliases for counters
# 'PROFILE_ALIAS': {'sn': 'TRIC_COUNTER_SERIAL_NUMBER', 'name': 'TRIC_TARIFF_NAME', 'max_increment': MAXIMUM_ALLOWED_COUNTER_READINGS_INCREMENT_PER_REPORT}
# get 'sn' and 'name' from https://lk.itpc.ru/#counters
TRIC_COUNTER_MAPPING = {
    'T1': {'sn': '09123456', 'name': 'Электроэнергия (День)', 'max_increment': 500},
    'T2': {'sn': '09123456', 'name': 'Электроэнергия (Ночь)', 'max_increment': 500}
}
