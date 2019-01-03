"""
Main code for furnace monitor
"""

# Imports
import machine
import network 
import ntptime
import socket
import time
import usyslog

# Constants
LAST_TIME_SYNC = 0


def log(config, message, severity=usyslog.S_INFO):
    host = config['syslog']['host']
    ts = get_timestamp(config)

    client = usyslog.UDPClient(ip=host)
    client.log(severity, message)
    client.close()


def read_config():
    creader = open('config.ini', 'r')
    section='default'
    conf_data = {}
    for idx, line in enumerate(creader.readlines()):
        line = line.strip()

        # Blank line - ignore it
        if line == '':
            continue

        # Comment line - ignore it
        elif line[0] == '#':
            continue

        # Section line
        elif line[0] == '[' and line[-1] == ']':
            section = line[1:-1]
            conf_data.setdefault(section, dict())

        elif ' = ' not in line:
            print("Invalid format, line {}:\n{}".format(idx, line))

        # Hopefully a setting for the section
        else:
            parsed = line.split(' = ')
            conf_data[section][parsed[0]] = parsed[1]

    print(conf_data)
    return conf_data


def setup_network(config):
    """
    Connect to the wifi network, using creds from the config file
    """
    sta_if = network.WLAN(network.STA_IF)

    if not sta_if.isconnected():
        sta_if.active(True)
        sta_if.connect(config['wifi']['ssid'], config['wifi']['password'])

        while not sta_if.isconnected():
            pass

        log(config, "Network activated")

    print("Ifconfig: {}".format(sta_if.ifconfig()))
    sync_time(config)


def reset_network(config):
    """
    Take down the network interface and fire it back up
    """

    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(False)
    setup_network(config)

def sync_time(config):
    """
    Attempts to sync the local time via ntp
    """

    global LAST_TIME_SYNC

    # Only sync every 10 minutes or so
    if time.time() - LAST_TIME_SYNC < (10 * 60):
        return

    synced = False
    attempts = 0
    max_attempts = int(config['ntp']['attempts'])

    while not synced and attempts < max_attempts:
        try:
            ntptime.settime()
        except Exception:
            pass
        else:
            synced = True
            LAST_TIME_SYNC = time.time()

        attempts += 1

def get_timestamp(config):
    """
    Get a unix epoch timestamp
    """

    # The ESP8266 uses a different base for its epoch - it uses Jan 1, 2000.  To convert to a more
    # useful format, we'll add that value to the timestamp here
    return time.time() + 946684800

def toggle_board_led(val="toggle"):
    board_led = machine.Pin(2, machine.Pin.OUT)

    if val == "toggle":
        board_led.value(not board_led.value())
    if val is True:
        board_led.value(False)
    if val is False:
        board_led.value(True)

def categorize_data(config, data):
    results = {
        'no': 0,
        'maybe': 0,
        'yes': 0
    }

    for key in data:
        if key < int(config['rumble']['no_top']):
            results['no'] += data[key]
        elif key < int(config['rumble']['maybe_top']):
            results['maybe'] += data[key]
        else:
            results['yes'] += data[key]

    return results

def monitor_loop(config):
    """
    Loop, monitoring the vibration sensor and occasionally sending data out
    """
    adc_pin = int(config['monitor']['pin'])
    loop_delay = float(config['monitor']['delay'])

    adc = machine.ADC(adc_pin)
    last_blink = 0

    while 1:
        data = {}
        start = time.time()

        while time.time() - start < 10:
            if time.time() - last_blink >= 1:
                last_blink = time.time()
                toggle_board_led()

            value = adc.read()
            data.setdefault(value, 0)
            data[value] += 1

            time.sleep(loop_delay)

        l_data = []
        for key in sorted(data):
            l_data.append("{}:{}".format(key, data[key]))
        log_msg = ', '.join(l_data)
        log(config, "Raw reads: |{}|".format(log_msg))
        categorized = categorize_data(config, data)
        print(categorized)

        send_data(config, categorized)

def send_data(config, categorized):
    """
    Send categorized data to graphite
    """
    
    setup_network(config)
    ts = get_timestamp(config)

    addr_info = socket.getaddrinfo("code-energy.com", 2003)
    addr = addr_info[0][-1]

    s = socket.socket()
    s.connect(addr)

    for category in ('no', 'maybe', 'yes'):
        name = 'iot.home.oilburner.{}'.format(category)
        line = '{} {} {}\n'.format(name, categorized[category], ts)
        print("Sending line: {}".format(line))
        s.send(line)
    s.close()

if __name__ == '__main__':
    config = read_config()
    setup_network(config)
    monitor_loop(config)