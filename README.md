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
