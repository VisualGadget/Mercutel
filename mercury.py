from machine import Pin, UART
import utime
import struct
import math
import uos

import utils

DOWS = ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Holiday')
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')


class MercuryEnergyMeter:
    '''
    Mercury 200 energy meter driver
    '''
    class COMMAND:
        SET_DATE_TIME = 0x02
        SET_SPEED = 0x08
        GET_DATE_TIME = 0x21
        GET_ENERGY = 0x27
        GET_SERIAL_NUMBER = 0x2F
        GET_UIP = 0x63

    SUPPORTED_PORT_SPEEDS = (9600, 4800, 2400, 1200, 600)

    class UART0Ctx:
        def __init__(self, em):
            self._em = em

        def __enter__(self):
            self._em._get_UART0()

        def __exit__(self, *args):
            self._em._release_UART0()

    def __init__(self, addr: int, port_speed: int, pin_txe: int, pin_rx: int, pin_tx: int):
        self.addr = addr
        self._pin_txe = Pin(pin_txe, Pin.OUT, value=0)  # RS-485 tx/rx control
        self._pin_tx = Pin(pin_tx, Pin.OUT)
        self._pin_rx = Pin(pin_rx, Pin.IN, Pin.PULL_UP)
        self._port_speed = port_speed
        self._uart = UART(0)
        self._uart_ctx = self.UART0Ctx(self)

    def _uart_init(self):
        self._uart.init(baudrate=self._port_speed, bits=8, parity=None, stop=1, tx=self._pin_tx, rx=self._pin_rx, timeout=400, rxbuf=50)

    def _get_UART0(self):
        uos.dupterm(None, 1)  # disable stdout to UART0, release UART0.read()
        # micropython.kbd_intr(-1)
        self._uart_init()

    def _release_UART0(self):
        uos.dupterm(UART(0, 115200), 1)  # redirect all output to UART0, breaks UART0.read()
        # micropython.kbd_intr(3)

    @staticmethod
    def _crc16(data: bytes) -> int:
        '''
        CRC-16 Modbus hashing algorithm
        '''
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                lsb = crc & 1
                crc >>= 1
                if lsb:
                    crc ^= 0xA001
        return crc

    @staticmethod
    def bcd_decode(data: bytes, decimals: int = 0):
        '''
        Decode BCD number
        '''
        res = 0
        shift = 10**(-decimals)
        for b in reversed(data):
            res += (b & 0x0F) * shift
            shift *= 10
            res += (b >> 4) * shift
            shift *= 10
        return res

    @staticmethod
    def bcd_encode(value: int, b_size: int) -> bytes:
        '''
        Encode unsigned int to BCD
        '''
        assert value >= 0
        res = bytearray(b_size)
        sval = str(value)
        for n in range(-1, -b_size * 2 - 1, -1):
            digit = int(sval[n]) if n >= -len(sval) else 0
            res[n // 2] |= digit if n % 2 else digit << 4
        return bytes(res)

    def _write(self, data: bytes):
        self._pin_txe.on()
        self._uart.write(data)
        bytes_per_s = self._port_speed / 10  # 10 baud per byte
        delay_us = len(data) / bytes_per_s * 1000000
        utime.sleep_us(int(delay_us))  # uart_wait_tx_done simulation
        self._pin_txe.off()

    def _send_data(self, cmd: int, body: bytes, addr: int = None):
        # ADDR-CMD-BODY-CRC
        if addr is None:
            addr = self.addr
        packet = struct.pack('>I', addr) + struct.pack('B', cmd)
        if body is not None:
            packet += body
        packet += struct.pack('<H', self._crc16(packet))
        self._write(packet)

    def _read_data(self, cmd: int, nbytes_body: int):
        # ADDR-CMD-BODY-CRC
        total_len = 4 + 1 + nbytes_body + 2

        answer = self._uart.read(total_len)

        if not answer:
            return 'no answer'

        alen = len(answer)
        if alen < 7:
            return f'too short answer of {alen} bytes: {answer}'

        r_crc = struct.unpack('<H', answer[-2:])[0]
        if r_crc != self._crc16(answer[:-2]):
            return 'wrong CRC'

        r_addr, r_cmd = struct.unpack('>IB', answer[:5])
        if r_addr != self.addr:
            return 'wrong addr'

        if r_cmd != cmd:
            return 'wrong cmd'

        return answer[5:-2]


    def _talk(self, cmd: int, body: bytes = None, answer_format: str = ''):
        for n in range(1, 100):
            with self._uart_ctx:
                self._send_data(cmd, body)
                expected_nbytes = struct.calcsize(answer_format)
                answer = self._read_data(cmd, expected_nbytes)

            utime.sleep_ms(10)  # maintains timeout between requests

            if isinstance(answer, str):  # error message
                error = answer
            else:
                if len(answer) == expected_nbytes:
                    return struct.unpack(answer_format, answer)
                else:
                    error = 'wrong answer length'
            print(f'#{n}: {error}')
            utils.watchdog.feed()

    def _ping_address(self, addr: int):
        '''
        Send arbitrary request to check address availability
        '''
        self._send_data(self.COMMAND.GET_SERIAL_NUMBER, None, addr=addr)

    def _any_answer(self) -> bool:
        '''
        Check for ping response
        '''
        signal = bool(self._uart.any())
        if signal:
            self._uart.read()  # clear rx buffer
        return signal

    @property
    def port_speed(self):
        return self._port_speed

    @port_speed.setter
    def port_speed(self, speed: int):
        '''
        Set meter port speed: 9600, 4800, 2400, 1200, 600
        '''
        # ADDR-CMD-speed[1]-CRC -> ADDR-CMD-CRC
        assert speed in self.SUPPORTED_PORT_SPEEDS
        spd_div = int(math.log(9600 // speed, 2))
        data = bytes([spd_div])
        answ = self._talk(self.COMMAND.SET_SPEED, data)
        # if answ is not None:  # doesn't work, always unreadable response
        self._port_speed = speed

    @property
    def energy(self) -> dict:
        # ADDR-CMD-CRC -> ADDR-CMD-count[BCD,4]*4-CRC
        data = self._talk(self.COMMAND.GET_ENERGY, answer_format='16B')
        if data:
            res = tuple(self.bcd_decode(data[n: n + 4], 2) for n in range(0, len(data), 4))
            return dict(zip(('T1', 'T2', 'T3', 'T4'), res))

    @property
    def uip(self) -> dict:
        # ADDR-CMD-CRC -> ADDR-CMD-V[BCD,2]-I[BCD,2]-P[BCD,3]-CRC
        data = self._talk(self.COMMAND.GET_UIP, answer_format='7B')
        if data:
            res = {
                'U': self.bcd_decode(data[:2], 1),
                'I': self.bcd_decode(data[2:4], 2),
                'P': self.bcd_decode(data[4:], 0)
            }
            return res

    @property
    def serial_number(self) -> int:
        # ADDR-CMD-CRC -> ADDR-CMD-serial[4]-CRC
        data = self._talk(self.COMMAND.GET_SERIAL_NUMBER, answer_format='>I')
        if data:
            return data[0]

    @property
    def date_time(self):
        # ADDR-CMD-CRC -> ADDR-CMD-timedate[BCD,7]-CRC
        data = self._talk(self.COMMAND.GET_DATE_TIME, answer_format='7B')
        if data:
            dec_data = list(map(lambda b: self.bcd_decode([b]), data))
            dec_data[0] = DOWS[dec_data[0]]
            dec_data[5] = MONTHS[dec_data[5] - 1]
            return dict(zip(('dow', 'hh', 'mm', 'ss', 'dd', 'mo', 'yy'), dec_data))

    def set_date_time(self, yy: int, mo: int, dd: int, hh: int, mm: int, ss: int, dow: int) -> bool:
        # ADDR-CMD-timedate[BCD,7]-CRC -> ADDR-CMD-CRC
        td = [(dow + 1) % 7, hh, mm, ss, dd, mo, yy]
        data = bytes(map(lambda v: self.bcd_encode(v, 1)[0], td))
        answer = self._talk(self.COMMAND.SET_DATE_TIME, data)
        return answer is not None

    def sync_date_time(self) -> bool:
        '''
        Syncronize clock and calendar with NTP server
        '''
        tm = utils.sync_time()
        return self.set_date_time(*tm[:-1])

    def bruteforce_network_address(self, start: int = 0, stop: int = 2**32 - 1, continue_session: bool = True):
        '''
        Search for occupied network addresses
        '''
        FILE = 'bf.log'
        r_start = start
        found_addresses = set()
        fmode = 'r+' if continue_session and FILE in uos.listdir() else 'w+'
        with open(FILE, fmode) as f:
            if continue_session:
                addr = None
                for line in f:  # read the last line
                    parts = line.rstrip('\n').split('-')
                    addr = int(parts[0])
                    if len(parts) == 2 and 'found' in parts[1]:
                        found_addresses.add(addr)
                if addr is not None:
                    r_start = max(start, addr + 1)

            while True:
                print(f'Searching for addresses in range [{r_start}, {stop}]')
                for addr in range(r_start, stop + 1):
                    with self._uart_ctx:
                        self._ping_address(addr)
                        utime.sleep_ms(10)
                        answer = self._any_answer()
                    if answer:
                        addr_found = addr - 1  # asking too fast so that's an answer to the previous request
                        print(f'Gotcha! Address {addr_found} is found')
                        f.write(f'{addr_found} - Gotcha! Address is found\n')
                        f.flush()
                        found_addresses.add(addr_found)
                    if not addr % 1000:
                        it_num = stop - r_start + 1
                        progress = ((addr - r_start + 1) / it_num if it_num > 0 else 1) * 100
                        status = f'{addr}, {progress:.1f}%'
                        if found_addresses:
                            status += f', found addresses: {found_addresses}'
                        print(status)
                    if addr > r_start and not addr % 50000:
                        f.write(f'{addr}\n')  # save progress
                        f.flush()
                    utils.watchdog.feed()
                r_start = start
