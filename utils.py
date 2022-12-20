import machine
import ntptime
import utime
import urandom

import config


if config.WDT_ENABLE:
    print('using watchdog')
    wdt_class = machine.WDT
else:
    # fake watchdog
    class WDT:
        def feed(self):
            pass
    wdt_class = WDT

watchdog = wdt_class()  # global use instance

def sleep_s(interval: int):
    watchdog.feed()
    for _ in range(interval):
        utime.sleep(1)
        watchdog.feed()

def randInt(min: int, max: int):
    return int(round(urandom.getrandbits(8) / 255 * (max - min) + min))

def retry_on_error(func):
    def looped_call(*args, **kwargs):
        n = 1
        while True:
            if n > 1:
                print(f'Attempt #{n}')
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if n > 50:
                    raise e
                print(f'Function {str(func)} failed {n} times')
                sleep_s(n)
                n += 1
    return looped_call

@retry_on_error
def sync_time():
    '''
    Syncronize local time with NTP server
    '''
    ntptime.host = f'{randInt(0, 3)}.ru.pool.ntp.org'
    print(f'begin clock synchronization using {ntptime.host}')
    t = ntptime.time()
    tz_sec = config.TIMEZONE * 60 * 60
    tm = utime.localtime(t + tz_sec)
    tm = tm[0:3] + (0,) + tm[3:6] + (0,)
    machine.RTC().datetime(tm)
    print('clock is synchronized')
