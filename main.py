import config
from mercury import MercuryEnergyMeter
from mqtt import MQTTElectricityMeter
# import tric
import utils


# if not config.DEBUG:
#     def print(*args, **kwargs):
#         pass

def create_emeter(port_speed = 9600) -> MercuryEnergyMeter:
    return MercuryEnergyMeter(config.ECOUNTER_NETWORK_ADDRESS, port_speed, config.PIN_TXE, config.PIN_RX, config.PIN_TX)

def set_meter_speed(speed):
    em = create_emeter()
    for cur_speed in em.SUPPORTED_PORT_SPEEDS:
        em.port_speed = cur_speed
        em.port_speed = speed
        utils.watchdog.feed()

def create_emeter_auto_speed() -> MercuryEnergyMeter | None:
    em = create_emeter()
    for cur_speed in em.SUPPORTED_PORT_SPEEDS:
        em.port_speed = cur_speed
        if em.serial_number:
            return em
        utils.watchdog.feed()

    return None

def main():
    print('Mercutel')
    print(f'Energy meter: {config.ECOUNTER_NETWORK_ADDRESS}')

    speed = 600
    # set_meter_speed(speed)
    em = create_emeter(speed)

    # while True:
    #     a = em.serial_number
    #     print(a)
    #     utils.sleep_s(1)

    # print(em.sync_date_time())
    dt = em.date_time
    if dt:
        print(f"{dt['hh']:02}:{dt['mm']:02}:{dt['ss']:02}, {dt['dow']}, {dt['mo']} {dt['dd']}, 20{dt['yy']}")

    mqttm = MQTTElectricityMeter(config.MQTT_SERVER, config.MQTT_USER, config.MQTT_PASSWORD)

    n = 0
    while True:

        if not n % 5:  # every 5 minutes
            state = {}

            uip = em.uip
            if uip:
                state.update(uip)

            energy = em.energy
            if energy:
                energy12 = {tariff: value for tariff, value in energy.items() if tariff in config.TRIC_COUNTER_MAPPING}
                state.update(energy12)
                # if not n % (24 * 60): # 1 day
                #     # does not work until uPython ESP8266 port fix SSL implementation https://github.com/micropython/micropython-lib/issues/400
                #     tric.send_counter_readings(energy12)

            print(state)
            if state:
                print('before send_update')
                mqttm.send_update(state)
                print('after send_update')

        n += 1
        print('sleep 60')
        utils.sleep_s(60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        import uos
        import machine
        # restore REPL
        u0 = machine.UART(0, 115200)
        uos.dupterm(u0, 1)
        print('Ctrl-C detected. Restarting...')
        machine.reset()
