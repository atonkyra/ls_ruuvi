# ls_ruuvi
less sucky ruuvitag_exporter, the old one that I used to have somewhere always died and got stuck (also used deprecated hciconfig/hcidump)

## how does it do it!?
SCREENSCRAPING, DIRTY AMOUNT OF IT (bluetoothctl and btmon)

## how do i use it
```
python3 ls_ruuvi.py -i 0 -p 9999
```

And verify results with
```
curl 127.0.0.1:9999
```

## trubbleshooting
add print() calls

good event looks something like this
```
> HCI Event: LE Meta Event (0x3e) plen 37                                                                               #563 515.638414
      LE Advertising Report (0x02)
        Num reports: 1
        Event type: Non connectable undirected - ADV_NONCONN_IND (0x03)
        Address type: Random (0x01)
        Address: FD:4F:1B:54:41:08 (Static)
        Data length: 25
        Flags: 0x04
          BR/EDR Not Supported
        Company: not assigned (1177)
          Data: 03511e4fc91c0070ff5c03f80b8900000000
        RSSI: -79 dBm (0xb1)

```
