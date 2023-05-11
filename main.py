import RPi.GPIO as GPIO #importem la llibreria correpsonent
from functions import *
from pyrf24 import RF24
from time import sleep
import os
from networkLib import *

radio = RF24(22, 0)
filename = ''
#filename_bytes = (False, b'')

GPIO.setmode(GPIO.BCM) #establim com es fara referencia als pins de la RPi

#Switch Pinout definition (OFF/ON) & Setup
SW1=13 #StandBy/Active
SW2=19 #IndividualMode/NetworkMode
SW3=26 #Rx/Tx
SW4=21 #Stop/Go
SW5=20 #-/ReadUSB
SW6=16 #-/WriteUSB
SW7=12 

GPIO.setup(SW1, GPIO.IN)
GPIO.setup(SW2, GPIO.IN)
GPIO.setup(SW3, GPIO.IN)
GPIO.setup(SW4, GPIO.IN)
GPIO.setup(SW5, GPIO.IN)
GPIO.setup(SW6, GPIO.IN)
GPIO.setup(SW7, GPIO.IN)


#LED Pinout definition & Setup
L1=2   #RED, active
L2=3   #YELLOW, rx if L2 & L3 NM
L3=27  #GREEN, tx if L2 & L3 NM
L4=24  #BLUE, read or write usb
L5=23  #BLUE, Network Mode

GPIO.setup(L1, GPIO.OUT)
GPIO.setup(L2, GPIO.OUT)
GPIO.setup(L3, GPIO.OUT)
GPIO.setup(L4, GPIO.OUT)
GPIO.setup(L5, GPIO.OUT)

On=True
Off=False

#tots els leds apagats al iniciar el programa
GPIO.output(L1, GPIO.LOW)
GPIO.output(L2, GPIO.LOW)
GPIO.output(L3, GPIO.LOW)
GPIO.output(L4, GPIO.LOW)
GPIO.output(L5, GPIO.LOW)

#definicio dels diferents estats necesaris per a fer el main.
def active():
    compressed_bytes_batches = []
    while (GPIO.input(SW1)==True):
        sleep(0.2)
        if (GPIO.input(SW5)==True): #Read file from USB
            led_manager(L1,Off)
            filename, compressed_bytes_batches = read_usb()
            led_manager(L1,On)
        elif (GPIO.input(SW6)==True): #Write file to USB
            led_manager(L1,Off)
            write_usb()
            led_manager(L1,On)
        elif (GPIO.input(SW2)==True and GPIO.input(SW3)==True and GPIO.input(SW4)==True): #NM Transmitter
            led_manager(L1,Off)
            led_manager(L3,On)
            transmitter()
            led_manager(L1,On)
            led_manager(L3,Off)
            led_manager(L5,Off)
        elif (GPIO.input(SW2)==True and GPIO.input(SW3)==False and GPIO.input(SW4)==True): #NM Receiver
            led_manager(L1,Off)
            led_manager(L3,On)
            receiver()
            led_manager(L1,On)
            led_manager(L3,Off)
            led_manager(L5,Off)
        elif (GPIO.input(SW4)==True and GPIO.input(SW2)==False and GPIO.input(SW3)==False): #Individual Mode Rx
            led_manager(L1,Off)
            rx_mode()
            led_manager(L1,On)
        elif (GPIO.input(SW4)==True and GPIO.input(SW2)==False and GPIO.input(SW3)==True): #Individual Mode Tx
            led_manager(L1,Off)
            tx_mode(filename, compressed_bytes_batches)
            led_manager(L1,On)
        elif (GPIO.input(SW7)==True):
            os.system('sudo reboot')
    
def read_usb():
    #AQUI cridar les funcions necesaries per a llegir del usb
    led_manager(L4,On)
    if os.path.exists('/dev/sda1'):
        os.system('sudo mount /dev/sda1 /media/rpi/USB')
    if os.path.exists('/dev/sdb1'):
        os.system('sudo mount /dev/sdb1 /media/rpi/USB')
    if os.path.exists('/dev/sdc1'):
        os.system('sudo mount /dev/sdc1 /media/rpi/USB')
    if os.path.exists('/dev/sdd1'):
        os.system('sudo mount /dev/sdd1 /media/rpi/USB')
    filename, compressed_bytes_batches = download_from_usb()
    led_manager(L2,On)
    os.system('sudo umount /media/rpi/USB')
    while (GPIO.input(SW5)==True):
        sleep(0.2)
        continue
    led_manager(L4,Off)
    led_manager(L2,Off)
    return filename, compressed_bytes_batches
    

def write_usb():
    led_manager(L4,On)
    if os.path.exists('/dev/sda1'):
        os.system('sudo mount /dev/sda1 /media/rpi/USB')
    if os.path.exists('/dev/sdb1'):
        os.system('sudo mount /dev/sdb1 /media/rpi/USB')
    if os.path.exists('/dev/sdc1'):
        os.system('sudo mount /dev/sdc1 /media/rpi/USB')
    if os.path.exists('/dev/sdd1'):
        os.system('sudo mount /dev/sdd1 /media/rpi/USB')
    #AQUI cridar les funcions necesaries per a escriure al usb
    print(filename_bytes)
    upload_to_usb(filename_bytes[1])
    led_manager(L2,On)
    os.system('sudo umount /media/rpi/USB')
    while (GPIO.input(SW6)==True):
        sleep(0.2)
        continue
    led_manager(L4,Off)
    led_manager(L2,Off)

def network_mode():
    
    led_manager(L3,On)
    led_manager(L5,On)
    #AQUI cridar les funcions necesaries per a executar el network mode
    if (GPIO.input(SW3)==True and GPIO.input(SW4)==True): #NM
        transmitter()#NM
    else:#NM
        receiver()#NM
    led_manager(L2,On)
    while (GPIO.input(SW4)==True):
        sleep(0.2)
        continue
    led_manager(L2,Off)
    led_manager(L3,Off)
    led_manager(L5,Off)

def tx_mode(filename, compressed_bytes_batches):
    led_manager(L3,On)
    #AQUI cridar les funcions necesaries per a executar el tx mode
    #radio = RF24(22, 0)

    #if not radio.begin():
    #    raise OSError("nRF24L01 hardware isn't responding")
    #radio_setup(12345, False)
    radioSetupTX()

    tx(frament_the_text(bytes(filename,'utf-16-le')))
    sleep(0.1)

    bytes_to_tx = frament_the_text(len(compressed_bytes_batches).to_bytes(31, byteorder='big'))

    #bytes_to_tx = frament_the_text(bytes(str(len(compressed_bytes_batches)), 'utf-16-le'))
    tx(bytes_to_tx)
    sleep(0.1)

    for compressed_bytes_batch in compressed_bytes_batches:
        payload = fragment_batches_into_packets(compressed_bytes_batch)
        ok = tx(payload)
        if (GPIO.input(SW4)==False):
            break
        #encendre leds en funció del valor de "ok"
        if ok:
            print("OK")
    #        #encendre un led
        elif not ok:
            print("NOT OK")
    #        #encendre un altre led
        sleep(0.1)
    led_manager(L2,On)
      
    radioPowerOff()
    
    while (GPIO.input(SW4)==True):
        sleep(0.2)
        continue
    led_manager(L2,Off)
    led_manager(L3,Off)
        
def rx_mode(): 
    global filename_bytes
    os.system('sudo rm /home/rpi/textfile/file.txt')
    led_manager(L3,On)
    radioSetupRX()
    filename_bytes = rx()
    print(filename_bytes)
    sleep(0.5)
    reception = rx()
    sleep(0.5)
    if(GPIO.input(SW4)==False):
          radioPowerOff()
          led_manager(L2,Off)
          led_manager(L3,Off)
          return
    number_of_fragments = int.from_bytes(reception[1], byteorder='big')

    for i in range(number_of_fragments):
        reception = rx()
        sleep(0.5)
        #encendre leds en funció del valor de "reception[0]"
        if(GPIO.input(SW4)==False):
          break
        if reception[0]:
            print("OK")
            #encendre un led
        elif not reception[0]:
            print("NOT OK")
            #encendre un altre led
        write(reception[1])
        #sleep(0.5)
    led_manager(L2,On)    
    
    radioPowerOff()
    
    while (GPIO.input(SW4)==True):
        sleep(0.2)
        continue
    led_manager(L2,Off)
    led_manager(L3,Off)

        
#estat de inici 
while True:
    sleep(2)
    if GPIO.input(SW1)==True:
        led_manager(L1,On)
        active()
        led_manager(L1,Off)
