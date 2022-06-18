import machine
import ntptime
import utime

import config


if config.WDT_ENABLE:
    wdt_class = machine.WDT
else:
    # fake watchdog
    class WDT:
        def feed(self):
            pass
    wdt_class = WDT

watchdog = wdt_class()  # global use instance

def sleep_s(interval: int):
    for _ in range(interval):
        utime.sleep(1)
        watchdog.feed()

def retry_on_error(func):
    def looped_call(*args, **kwargs):
        n = 1
        while True:
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
def sync_time() -> tuple:
    '''
    Syncronize local time with NTP server
    '''
    t = ntptime.time()
    tz_sec = config.TIMEZONE * 60 * 60
    tm = utime.localtime(t + tz_sec)
    tm2 = tm[0:3] + (0,) + tm[3:6] + (0,)
    machine.RTC().datetime(tm2)
    return tm
