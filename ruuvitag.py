"""
MIT License

Copyright (c) 2016 Tomi Tuhkanen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
# shamelessly stolen from https://github.com/ttu/ruuvitag-sensor

from __future__ import division

import base64
import math
import logging

log = logging.getLogger(__name__)


def get_decoder(data_type):
    '''
    Get correct decoder for Data Type.

    Returns:
        object: Data decoder
    '''
    if data_type == 2:
        return UrlDecoder()
    elif data_type == 3:
        return Df3Decoder()
    else:
        return Df5Decoder()

def twos_complement(value, bits):
    if (value & (1 << (bits - 1))) != 0:
        value = value - (1 << bits)
    return value

def rshift(val, n):
    '''
    Arithmetic right shift, preserves sign bit.
    https://stackoverflow.com/a/5833119 .
    '''
    return (val % 0x100000000) >> n


class UrlDecoder(object):
    '''
    Decodes data from RuuviTag url
    Protocol specification:
    https://github.com/ruuvi/ruuvi-sensor-protocols
    '''

    '''
    Decoder operations are ported from:
    https://github.com/ruuvi/sensor-protocol-for-eddystone-url/blob/master/index.html

    0:   uint8_t     format;          // (0x01 = realtime sensor readings)
    1:   uint8_t     humidity;        // one lsb is 0.5%
    2-3: uint16_t    temperature;     // Signed 8.8 fixed-point notation.
    4-5: uint16_t    pressure;        // (-50kPa)
    6-7: uint16_t    time;            // seconds (now from reset)

    The bytes for temperature, pressure and time are swaped during the encoding
    '''

    def _get_temperature(self, decoded):
        '''Return temperature in celsius'''
        temp = (decoded[2] & 127) + decoded[3] / 100
        sign = (decoded[2] >> 7) & 1
        if sign == 0:
            return round(temp, 2)
        return round(-1 * temp, 2)

    def _get_humidity(self, decoded):
        '''Return humidity %'''
        return decoded[1] * 0.5

    def _get_pressure(self, decoded):
        '''Return air pressure hPa'''
        pres = ((decoded[4] << 8) + decoded[5]) + 50000
        return pres / 100

    def decode_data(self, encoded):
        '''
        Decode sensor data.

        Returns:
            dict: Sensor values
        '''
        try:
            identifier = None
            if len(encoded) > 8:
                identifier = encoded[8:]
                encoded = encoded[:8]
            decoded = bytearray(base64.b64decode(encoded, '-_'))
            return {
                'temperature': self._get_temperature(decoded),
                'humidity': self._get_humidity(decoded),
                'pressure': self._get_pressure(decoded),
                'identifier': identifier
            }
        except:
            log.exception('Encoded value: %s not valid', encoded)
            return None


class Df3Decoder(object):
    '''
    Decodes data from RuuviTag with Data Format 3
    Protocol specification:
    https://github.com/ruuvi/ruuvi-sensor-protocols
    '''

    def _get_temperature(self, data):
        '''Return temperature in celsius'''
        temp = (data[2] & ~(1 << 7)) + (data[3] / 100)
        sign = (data[2] >> 7) & 1
        if sign == 0:
            return round(temp, 2)
        return round(-1 * temp, 2)

    def _get_humidity(self, data):
        '''Return humidity %'''
        return data[1] * 0.5

    def _get_pressure(self, data):
        '''Return air pressure hPa'''
        pres = (data[4] << 8) + data[5] + 50000
        return pres / 100

    def _get_acceleration(self, data):
        '''Return acceleration mG'''
        acc_x = twos_complement((data[6] << 8) + data[7], 16)
        acc_y = twos_complement((data[8] << 8) + data[9], 16)
        acc_z = twos_complement((data[10] << 8) + data[11], 16)
        return (acc_x, acc_y, acc_z)

    def _get_battery(self, data):
        '''Return battery mV'''
        return (data[12] << 8) + data[13]

    def decode_data(self, data):
        '''
        Decode sensor data.

        Returns:
            dict: Sensor values
        '''
        try:
            byte_data = bytearray.fromhex(data)
            acc_x, acc_y, acc_z = self._get_acceleration(byte_data)
            return {
                'humidity': self._get_humidity(byte_data),
                'temperature': self._get_temperature(byte_data),
                'pressure': self._get_pressure(byte_data),
                'acceleration': math.sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z),
                'acceleration_x': acc_x,
                'acceleration_y': acc_y,
                'acceleration_z': acc_z,
                'battery': self._get_battery(byte_data)
            }
        except Exception:
            log.exception('Value: %s not valid', data)
            return None

class Df5Decoder(object):
    '''
    Decodes data from RuuviTag with Data Format 5
    Protocol specification:
    https://github.com/ruuvi/ruuvi-sensor-protocols
    '''

    def _get_temperature(self, data):
        '''Return temperature in celsius'''
        if data[1:2] == 0x7FFF:
            return None

        temperature = twos_complement((data[1] << 8) + data[2], 16) / 200
        return round(temperature, 2)

    def _get_humidity(self, data):
        '''Return humidity %'''
        if data[3:4] == 0xFFFF:
            return None

        humidity = ((data[3] & 0xFF) << 8 | data[4] & 0xFF) / 400
        return round(humidity, 2)

    def _get_pressure(self, data):
        '''Return air pressure hPa'''
        if data[5:6] == 0xFFFF:
            return None

        pressure = ((data[5] & 0xFF) << 8 | data[6] & 0xFF) + 50000
        return round((pressure / 100), 2)

    def _get_acceleration(self, data):
        '''Return acceleration mG'''
        if (data[7:8] == 0x7FFF or
                data[9:10] == 0x7FFF or
                data[11:12] == 0x7FFF):
            return (None, None, None)

        acc_x = twos_complement((data[7] << 8) + data[8], 16)
        acc_y = twos_complement((data[9] << 8) + data[10], 16)
        acc_z = twos_complement((data[11] << 8) + data[12], 16)
        return (acc_x, acc_y, acc_z)

    def _get_powerinfo(self, data):
        '''Return battery voltage and tx power '''
        power_info = (data[13] & 0xFF) << 8 | (data[14] & 0xFF)
        battery_voltage = rshift(power_info, 5) / 1000 + 1.6
        tx_power = (power_info & 0b11111) * 2 - 40

        if rshift(power_info, 5) == 0b11111111111:
            battery_voltage = None
        if (power_info & 0b11111) == 0b11111:
            tx_power = None

        return (round(battery_voltage, 3), tx_power)

    def _get_battery(self, data):
        '''Return battery mV'''
        battery_voltage = self._get_powerinfo(data)[0]
        return battery_voltage

    def _get_txpower(self, data):
        '''Return transmit power'''
        tx_power = self._get_powerinfo(data)[1]
        return tx_power

    def _get_movementcounter(self, data):
        return data[15] & 0xFF

    def _get_measurementsequencenumber(self, data):
        measurementSequenceNumber = (data[16] & 0xFF) << 8 | data[17] & 0xFF
        return measurementSequenceNumber

    def _get_mac(self, data):
        return ''.join('{:02x}'.format(x) for x in data[18:24])

    def decode_data(self, data):
        '''
        Decode sensor data.

        Returns:
            dict: Sensor values
        '''
        try:
            byte_data = bytearray.fromhex(data)
            acc_x, acc_y, acc_z = self._get_acceleration(byte_data)
            return {
                'humidity': self._get_humidity(byte_data),
                'temperature': self._get_temperature(byte_data),
                'pressure': self._get_pressure(byte_data),
                'acceleration': math.sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z),
                'acceleration_x': acc_x,
                'acceleration_y': acc_y,
                'acceleration_z': acc_z,
                'tx_power': self._get_txpower(byte_data),
                'battery': self._get_battery(byte_data),
                'movement_counter': self._get_movementcounter(byte_data),
                'measurement_sequence_number': self._get_measurementsequencenumber(byte_data),
                'mac': self._get_mac(byte_data)
            }
        except Exception:
            log.exception('Value: %s not valid', data)
            return None

def get_data_format_2and4(raw):
    """
    Validate that data is from RuuviTag and is Data Format 2 or 4. Convert hexadcimal data to string.
    Encoded data part is after ruu.vi/# or r/
    Returns:
        string: Encoded sensor data
    """
    try:
        # TODO: Fix conversion so convered data will show https://ruu.vi/# and htts://r/
        # Now it has e.g. [Non_ASCII characters]ruu.vi/#AjwYAMFc
        base16_split = [raw[i:i + 2] for i in range(0, len(raw), 2)]
        selected_hexs = filter(lambda x: int(x, 16) < 128, base16_split)
        characters = [chr(int(c, 16)) for c in selected_hexs]
        data = ''.join(characters)

        # take only part after ruu.vi/# or r/
        index = data.find('ruu.vi/#')
        if index > -1:
            return data[(index + 8):]
        else:
            index = data.find('r/')
            if index > -1:
                return data[(index + 2):]
            return None
    except:
        return None

def get_data_format_3(raw):
    """
    Validate that data is from RuuviTag and is Data Format 3
    Returns:
        string: Sensor data
    """
    # Search of FF990403 (Manufacturer Specific Data (FF) / Ruuvi Innovations ltd (9904) / Format 3 (03))
    try:
        if "FF990403" not in raw:
            return None

        payload_start = raw.index("FF990403") + 6
        return raw[payload_start:]
    except:
        return None

def get_data_format_5(raw):
    """
    Validate that data is from RuuviTag and is Data Format 5
    Returns:
        string: Sensor data
    """
    # Search of FF990405 (Manufacturer Specific Data (FF) / Ruuvi Innovations ltd (9904) / Format 5 (05))
    try:
        if "FF990405" not in raw:
            return None

        payload_start = raw.index("FF990405") + 6
        return raw[payload_start:]
    except:
        return None
