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
        print(f'Error: authentication failed: {r.status_code}')
        return False

    tokens = r.json()

    # get counters state from TRIC
    bearer_auth = {'Authorization': f'Bearer {tokens["access_token"]}'}
    r = requests.get(f'https://terminal.itpc.ru/v2/counter/reading/{config.TRIC_ACCOUNT}/', headers=bearer_auth)
    if r.status_code != 200:
        print(f'Error: historical counter values reading error: {r.status_code}')
        return False

    counters = r.json()['counters']
    tric_counters = []
    tric_counter_name = {}
    for counter_info in counters:
        reported_value_source = counter_info['current']
        if not reported_value_source:
            reported_value_source = counter_info['previous']
        reported_value = float(reported_value_source['value']) if reported_value_source else None
        tric_counters.append({'serial': counter_info['serial'], 'name': counter_info['service']['name'], 'id': counter_info['oid'], 'last_reported_value': reported_value})
        tric_counter_name[counter_info['oid']] = counter_info['service']['name']

    # prepare report
    readings_to_send = {}
    counter_increment = {}
    for counter_measurement, current_readings in counter_readings.items():
        home_counter = config.TRIC_COUNTER_MAPPING.get(counter_measurement)
        if not home_counter:
            print(f'Warning: counter profile "{counter_measurement}" is absent in TRIC_COUNTER_MAPPING')
            continue

        counter_name = home_counter['name']
        counter_sn = home_counter['sn']
        counter_max_inc = home_counter['max_increment']
        for tric_counter in tric_counters:
            if tric_counter['serial'] == counter_sn and tric_counter['name'] == counter_name:
                reported_readings = tric_counter['last_reported_value']
                if reported_readings is None or (reported_readings <= current_readings <= reported_readings + counter_max_inc and ('tric_counter' not in home_counter or reported_readings > home_counter['tric_counter']['last_reported_value'])):
                    home_counter['tric_counter'] = tric_counter

        hctc = home_counter.get('tric_counter')
        if hctc is None:
            print(f'Warning: unable to map counter #{counter_sn} "{counter_name}" to a TRIC counter')
            continue

        counter_id = hctc['id']
        if counter_id in readings_to_send:
            print('Error: several counters are mapped to a one TRIC counter')
            return False

        readings_to_send[counter_id] = str(current_readings)
        reported_readings = hctc['last_reported_value']
        if reported_readings is not None:
            counter_increment[counter_id] = current_readings - reported_readings

    # send report
    if not readings_to_send:
        print('Warning: nothing to report')
        return False

    r = requests.put(f'https://terminal.itpc.ru/v2/counter/reading/{config.TRIC_ACCOUNT}/', json=readings_to_send, headers=bearer_auth)
    if r.status_code != 200:
        print(f'Error: counter readins sending error: {r.status_code}')
        return False

    status = r.json()
    for cat in ('passed', 'skipped', 'failed'):
        counters_id = status[cat]
        if counters_id:
            counters = []
            for cid in counters_id:
                counter_info = f'"{tric_counter_name[cid]}"'
                if cid in readings_to_send:
                    counter_info += f' {readings_to_send[cid]}'
                if cid in counter_increment:
                    counter_info += f' (+{counter_increment[cid]:.1f})'
                counters.append(counter_info)
            print(f'Counters {cat}:', ', '.join(counters))
    return status['status']


def main():
    if len(sys.argv) < 2:
        print(
            "Service to report counter readings to TRIC (https://itpc.ru)\n"
            "Instructions for use:\n"
            "1. Configure TRIC section settings in config.py\n"
            "2. Run example: 'python.exe .\\tric.py T1=2435.15 T2=100.1' where T1 and T2 are counter profiles from TRIC_COUNTER_MAPPING"
        )
        return
    readings = {}
    for arg in sys.argv[1:]:
        t, v = arg.split('=')
        readings[t] = float(v)
    send_counter_readings(readings)


if __name__ == '__main__':
    main()
