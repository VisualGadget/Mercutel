# Usage example: python.exe .\tric.py T1=2435.15 T2=100.1

import binascii
import sys
try:
    import requests
except ImportError:
    import urequests as requests

import config


TERMINAL_BASIC_AUTH = ('vrNL4sCToqpHqzhz', 'nncLOaQ1O7MuyCMY')


def to_base64(s: str) -> str:
    '''
    Convert string to BASE64 representation
    '''
    data = bytes(s, 'utf8')
    if sys.version_info >= (3, 6):
        res = binascii.b2a_base64(data, newline=False)
    else:
        res = binascii.b2a_base64(data)
    return res.decode()

def send_counter_readings(counter_readings: dict) -> bool:
    '''
    Publish counter readings to TRIC (https://itpc.ru)
    :param counter_readings: reported counters reading with keys from TRIC_COUNTER_MAPPING, e.g. {'T1': 1234.5, 'T2': 2456}
    :return: success status
    '''
    cred = to_base64(':'.join(TERMINAL_BASIC_AUTH))
    basic_auth = {'Authorization': f'Basic {cred}'}
    r = requests.post(
        'https://terminal.itpc.ru/v2/oauth/token/',
        headers=basic_auth,
        data={
            'grant_type': 'password',
            'username': config.TRIC_ACCOUNT,
            'password': config.TRIC_PASSWORD,
        }
    )
    if r.status_code != 200:
        print(f'Authentication error: {r.status_code}')
        return False
    tokens = r.json()

    # get counters state from TRIC
    bearer_auth = {'Authorization': f'Bearer {tokens["access_token"]}'}
    r = requests.get(f'https://terminal.itpc.ru/v2/counter/reading/{config.TRIC_ACCOUNT}/', headers=bearer_auth)
    if r.status_code != 200:
        print(f'Historical counter values reading error: {r.status_code}')
        return False
    counters = r.json()['counters']
    tric_counters = {}
    tric_counter_name = {}
    for counter_info in counters:
        reported_value_source = counter_info['current']
        if not reported_value_source:
            reported_value_source = counter_info['previous']
        reported_value = float(reported_value_source['value']) if reported_value_source else None
        tric_counters[(counter_info['serial'], counter_info['service']['name'])] = {'id': counter_info['oid'], 'last_reported_value': reported_value}
        tric_counter_name[counter_info['oid']] = counter_info['service']['name']

    # prepare report
    readings_to_send = {}
    conter_increment = {}
    for counter_measurement, current_readings in counter_readings.items():
        home_counter = config.TRIC_COUNTER_MAPPING[counter_measurement]
        counter_name = home_counter['name']
        counter_sn = home_counter['sn']
        tric_counter = tric_counters.get((counter_sn, counter_name))
        if not tric_counter:
            print(f'Counter #{counter_sn} "{counter_name}" is not registered in TRIC')
            continue
        counter_id = tric_counter['id']
        reported_readings = tric_counter['last_reported_value']
        if reported_readings is not None:
            increment = current_readings - reported_readings
            if increment < 0:
                print(f'Counter "{counter_name}" is skipped because of readings decrement: {increment}')
                continue
            elif increment > home_counter['max_increment']:
                print(f'Counter "{counter_name}" is skipped because of high readings increment: {increment}')
                continue
            conter_increment[counter_id] = increment
        readings_to_send[counter_id] = str(current_readings)

    # send report
    if not readings_to_send:
        print('Nothing to report')
        return False
    r = requests.put(f'https://terminal.itpc.ru/v2/counter/reading/{config.TRIC_ACCOUNT}/', json=readings_to_send, headers=bearer_auth)
    if r.status_code != 200:
        print(f'Counter readins sending error: {r.status_code}')
        return False
    status = r.json()
    for cat in ('passed', 'skipped', 'failed'):
        counters_id = status[cat]
        if counters_id:
            counters = []
            for id in status[cat]:
                counter_info = f'"{tric_counter_name[id]}"'
                if id in readings_to_send:
                    counter_info += f' {readings_to_send[id]} (+{conter_increment[id]})'
                counters.append(counter_info)
            print(f'Counters {cat}:', ', '.join(counters))
    return status['status']


if __name__ == '__main__':
    readings = {}
    for arg in sys.argv[1:]:
        t, v = arg.split('=')
        readings[t] = float(v)
    send_counter_readings(readings)
