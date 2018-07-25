import argparse
import subprocess
import queue
import threading
import time
import logging
import ruuvitag
from prometheus_client import start_http_server, Gauge
from prometheus_client.core import REGISTRY


logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(name)-12s %(message)s'
)
logger = logging.getLogger('ls_ruuvi')
parser = argparse.ArgumentParser(description='less shitty ruuvitag beacon catcher')
parser.add_argument('-i', '--index-controller', required=False, help='BT controller index', type=int, default=0)
parser.add_argument('-p', '--exporter-port', required=True, help='Prometheus Exporter port', type=int)
args = parser.parse_args()
registry_metrics = {}


class Executor(object):
    def __init__(self):
        self._process = None
        self._input_handler_thread = None
        self._input = queue.Queue()

    def _input_handler(self):
        while True:
            line = self._process.stdout.readline()
            if not line:
                break
            line = line.decode('ascii', errors='ignore').strip()
            self._input.put(line)

    def get_line(self):
        return self._input.get()

    def send_line(self, line):
        cmd = '%s\n' % line
        self._process.stdin.write(cmd.encode('ascii'))
        self._process.stdin.flush()

    def start_process(self, start_args):
        self._process = subprocess.Popen(start_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._input_handler_thread = threading.Thread(target=self._input_handler)
        self._input_handler_thread.daemon = True
        self._input_handler_thread.start()

    def stop_process(self):
        self._process.terminate()
        self._input_handler_thread.join()


def bluetoothctl_select_adapter(btr):
    btr.send_line('list')
    btr.send_line('version')
    idx = 0
    selected_controller = None
    while True:
        line = btr.get_line()
        if line.startswith('Version'):
            break
        if line.startswith('Controller'):
            _, controller, _ = line.split(' ', 2)
            if idx == args.index_controller:
                selected_controller = controller
                break
    if selected_controller is None:
        raise KeyError('controller by idx %i not found' % args.index_controller)
    logger.info('selecting controller %s', selected_controller)
    btr.send_line('select %s' % selected_controller)


def bluetoothctl_enable(btr):
    btr.send_line('power on')
    btr.send_line('scan on')


def handle_metrics(tag, m):
    global registry_metrics
    for key, value in m.items():
        if key not in registry_metrics:
            registry_metrics[key] = Gauge('ruuvi_%s' % key, ' ', ['sensor', 'identifier'], registry=REGISTRY)
        registry_metrics[key].labels(tag, 'n/a').set(value)


def handle_event(ev):
    if ev['type'] != 'le_meta':
        return
    if 'Data' not in ev:
        return
    if 'Address' not in ev:
        return
    if 'Event type' not in ev or 'ADV_NONCONN_IND' not in ev['Event type']:
        return
    if 'Company' not in ev or '(1177)' not in ev['Company']:
        return
    ev_data = 'FF9904%s' % ev['Data'].upper()
    data = ruuvitag.get_data_format_2and4(ev_data)
    if data is not None:
        d = ruuvitag.UrlDecoder().decode_data(data)
        handle_metrics(ev['Address'], d)
        handle_metrics(ev['Address'], {'last_seen': time.time()})
        return
    data = ruuvitag.get_data_format_3(ev_data)
    if data is not None:
        d = ruuvitag.Df3Decoder().decode_data(data)
        handle_metrics(ev['Address'], d)
        handle_metrics(ev['Address'], {'last_seen': time.time()})
        return
    data = ruuvitag.get_data_format_5(ev_data)
    if data is not None:
        d = ruuvitag.Df5Decoder().decode_data(data)
        handle_metrics(ev['Address'], d)
        handle_metrics(ev['Address'], {'last_seen': time.time()})
        return


def btmon_loop(btr):
    ev = None
    while True:
        line = btr.get_line()
        if line.startswith('> HCI Event'):
            if ev is not None:
                handle_event(ev)
            if 'LE Meta Event' in line:
                ev = {'type': 'le_meta'}
            else:
                ev = {'type': 'unhandled'}
        else:
            if ev is None or ev['type'] == 'unhandled':
                continue
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                if key == 'LE Address' or key == 'Address':
                    value_splitted = value.split(' ', 1)
                    value = value_splitted[0]
                ev[key] = value


def main():
    bluetoothctl_runner = Executor()
    bluetoothctl_runner.start_process(['bluetoothctl'])
    bluetoothctl_select_adapter(bluetoothctl_runner)
    bluetoothctl_enable(bluetoothctl_runner)
    start_http_server(args.exporter_port)
    btmon_runner = Executor()
    btmon_runner.start_process(['btmon', '-i', '%s' % args.index_controller])
    btmon_loop(btmon_runner)


if __name__ == '__main__':
    main()
