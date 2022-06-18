import json
import ubinascii
import network
import umqtt.simple
import utils


class MQTTElectricityMeter:
    '''
    Home Assistant MQTT electricity meter device
    '''
    def __init__(self, server: str, user: str, password: str):
        mac = ubinascii.hexlify(network.WLAN().config('mac')).decode()
        device = {
            'manufacturer': 'dIcEmAN',
            'model': 'Mercury 200 telemetry',
            'name': 'Mercutel',
            'identifiers': mac
        }
        self.measured_parameters = {
            'U': {
                'device_class': 'voltage',
                'unit_of_measurement': 'V',
                'expire_after': 15 * 60  # 15 minutes
            },
            'I': {
                'device_class': 'current',
                'unit_of_measurement': 'A',
                'expire_after': 15 * 60
            },
            'P': {
                'device_class': 'power',
                'unit_of_measurement': 'W',
                'expire_after': 15 * 60
            },
            'T1': {
                'device_class': 'energy',
                'unit_of_measurement': 'kWh',
                'state_class': 'total_increasing',
                'expire_after': 24 * 60 * 60  # 1 day
            },
            'T2': {
                'device_class': 'energy',
                'unit_of_measurement': 'kWh',
                'state_class': 'total_increasing',
                'expire_after': 24 * 60 * 60
            }
        }
        self._mqtt = umqtt.simple.MQTTClient('Electricity Meter', server, user=user, password=password)
        self._connect()
        for param_name, sensor_info in self.measured_parameters.items():
            uid = f'EMeter_{mac[-4:]}_{param_name}'
            sensor_info['name'] = f'Electricity {param_name}'
            sensor_info['unique_id'] = uid
            sensor_info['state_topic'] = f'Household/electricity/{uid}/state'
            sensor_info['device'] = device
            # sensor_info['force_update'] = True
            # HA MQTT discovery
            ha_discovery_topic = f'homeassistant/sensor/{uid}/config'
            self._mqtt.publish(ha_discovery_topic, json.dumps(sensor_info), True)
        self._mqtt.disconnect()

        # self._mqtt.set_callback(self._inbox)

    @utils.retry_on_error
    def _connect(self):
        self._mqtt.connect(clean_session=False)

    def send_update(self, parameters: dict):
        self._connect()
        for param_name, param_value in parameters.items():
            self._mqtt.publish(self.measured_parameters[param_name]['state_topic'], str(param_value))
        self._mqtt.disconnect()

    # def _inbox(self, topic, msg):
    #     topic = topic.decode()
    #     if topic == self.config['command_topic']:
    #         data = json.loads(msg)
    #         self.on = data['state'] == STATES[True]
    #         self._send_update()
