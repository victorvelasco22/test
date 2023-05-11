from pyrf24 import RF24, rf24
import pandas as pd
import time
import logging
from todoLib import *

logging.basicConfig( encoding='utf-8', level=logging.DEBUG,format='[%(asctime)s] %(message)s')

#Array of link addresses (5 bytes each)
LINK_ADDRESSES = [NODE_A1, NODE_A2, NODE_B1, NODE_B2, NODE_C1, NODE_C2]

LINK_ADDRESSES.remove(OWN_ADDRESS) 
logging.info("My Own address is %s", OWN_ADDRESS)
#Packet size
PACKET_SIZE = 32

#End of transmission message
EOT = [226, 144, 151]
EOT_BYTES = bytes(EOT)

#Timeout
TIMEOUT_FILE = 10
TIMEOUT_TOKEN = 1
TIMEOUT_STATUS = 2
TIMEOUT_STATUS_REPLY = 2

#Global Table with the reachable transceivers
tb = pd.DataFrame(columns=['Address', 'Token', 'File'])

#Token Info, Each transceiver must know if it has had the token or not
token = 0

#File Info, Each TR must know if it has the file or not
file = 0

#These packets have no payload, header=packet
TOKEN_PACKET = b'\x0D'

#Headers for packets that need to be built each time they are sent (updated info)
HEADER_STATUS = b'\x0A'
HEADER_STATUS_PACKET_REPLY = b'\x0B'
HEADER_FILE_PACKET = b'\x0C'

def transmitter():
    """
    Initializes file and token value to 1
    Initializes radio
    Calls sendStatus()
    Calls sendFile()
    Calls sendToken()
    """
    
    global file, token
    
    file = 1
    token = 1

    radio = initializeRadio()
    radio.payload_size = 32
    radio.channel = 26 #6A 20
    radio.data_rate = rf24.RF24_250KBPS
    radio.set_pa_level(rf24.rf24_pa_dbm_e.RF24_PA_HIGH)
    radio.dynamic_payloads = True
    radio.set_auto_ack(True)
    radio.ack_payloads = False
    radio.set_retries(5, 15) 
    radio.listen = False

    logging.info("I currently have the role of transmitter.")
    tokenpassed = False
    while not tokenpassed:
        sendStatus(radio)
        while tb.empty:
            sendStatus(radio)
      
    filename = readFile()
    
    sendFile(radio,filename)
    if not tb.empty:
        while not sendToken(radio):
            continue
        tokenpassed = True

    del radio
    time.sleep(0.5)
    receiver()
    
    

#this function has to be executed every time the TR is passed the token
def sendStatus(radio):
    """
    Sends Status Packet to every Link Addresses with TIMEOUT_STATUS
    If there is response the open rx pipe and listen for response with TIMEOUT_STATUS_REPLY
    Stores info in a Table together with the corresponding link address. 
        If link address already in table update values, otherwise add new row
    """

    global tb

    logging.info("Sending status query to all nodes on my list, to see whoch ones respond.")
    
    for address in LINK_ADDRESSES:
        radio.listen = False
        radio.open_tx_pipe(address)
        response = False
        timed_out = False
        start_time = time.time()
        radio.flush_tx()
        radio.flush_rx()
        while not response and not timed_out:
            response = radio.write(HEADER_STATUS+OWN_ADDRESS)
            timed_out = (time.time() - start_time > TIMEOUT_STATUS)
        
        if response:
            logging.info("Obtained AUTOACK response from link address: %s", address)
            logging.info("Going to swap to RX role on this link in order to receive the status.")
            radio.listen = True
            radio.open_rx_pipe(1, OWN_ADDRESS)
            time.sleep(0.5) 
            timed_out = False
            start_time = time.time()
            while not radio.available() and not timed_out:
                time.sleep(1/1000)
                timed_out = (time.time() - start_time > TIMEOUT_STATUS_REPLY)
               
            if radio.available():
                answer_packet = radio.read(radio.get_dynamic_payload_size())
                radio.listen = False
                radio.close_rx_pipe(1)
                time.sleep(0.5)
                if answer_packet[0].to_bytes(1, byteorder='big') == HEADER_STATUS_PACKET_REPLY:
                    
                    file_status = answer_packet[1]
                    token_status = answer_packet[2]
                    logging.info("Received status reply correctly! With 'file_status' = %d and 'token_status' = %d", answer_packet[1], answer_packet[2])
                    if address in tb['Address'].values:
                        tb.loc[tb['Address'] == address,['File']] = file_status
                        tb.loc[tb['Address'] == address,['Token']] = token_status
                    else:
                        new_row = {'Address':address, 'File': file_status, 'Token':token_status}
                        tb.loc[len(tb)] = new_row
        else:
            logging.info("Link address %s, timed out while querying status. Skpping to next address.", address )
                        
    logging.info('Node Table at status query:')
    logging.info('\n\t' + tb.to_string().replace('\n', '\n\t'))              
            


def sendFile(radio,filename):
    """
    Send File to transceivers that do not have it already. (Check table)
    If TR stops responding ACKs keep trying during Timeout (think best value).
    If a TR timeouts, eliminate from tb so token is not passed to it.
    """
    global tb

    logging.info("Going to send the file to the nodes that don't have it yet.")
    file = readFile(filename)
    timed_out = False
    for index, row in tb.iterrows():
        if row['File'] == 0:
            radio.open_tx_pipe(row['Address'])
            logging.info("Sending file to link with address: %s",row['Address'])
            packet_id = b'\x00'
            start_time = time.time()
            timed_out = False
            
            for i in range(0, len(file),PACKET_SIZE-2):
                message = HEADER_FILE_PACKET + packet_id + file[i:i+PACKET_SIZE-2]
                response=False
                while (not response and not timed_out):
                    response = radio.write(message)
                    timed_out = (time.time() - start_time > TIMEOUT_FILE)

                if timed_out:
                    tb = tb.drop(index)
                    logging.info("Node with link address %s (index %d on table) timed out. Deleting his entry from table. Breaking", row['Address'], index)
                    break
                
                int_value = int.from_bytes(packet_id, byteorder='big')  # convert byte to integer
                logging.debug("Correclty sent file fragment %d", int_value)
                if int_value == 255:
                    int_value = 0
                else:
                    int_value += 1  # increment integer
                packet_id = int_value.to_bytes(1, byteorder='big')  # convert integer back to byte
            
            if not timed_out:
                end_packet = HEADER_FILE_PACKET + packet_id + EOT_BYTES
                response = False
                while (not response and not timed_out):
                    response = radio.write(end_packet)
                    timed_out = (time.time() - start_time > TIMEOUT_FILE)
                if response:
                    logging.info("EOT correclty transimted for file tx.")
                    logging.info("Going to put that node with link address %s (index %d) has correctly received the file", row['Address'], index )
                    tb.loc[index, ['File']] = 1
            else:
                logging.info("EOT timed out (no auto ack received)!!!!")
    
    logging.debug('timed_out:'+str(timed_out))


def sendToken(radio):
    """
    Send Token to TR and keep retrying (Timeout= 5-10 s)
    Look table col 'Token' for priority: First TR with value 0, then TR with value 1 in first position
    If Token is sent to a TR with 'token' = 0, 'token' value is updated to 1 and TR is sent to the last row
    If Token is sent to a TR with 'token' = 1, 'token' TR is sent to the last row
    Returns True if token is passed to another node, False otherwise.
    """
    global tb
    token_passed = False

    if 0 in tb['Token'].values:
        for index, row in tb.iterrows():
            new_row = {'Address':row['Address'], 'File': row['File'], 'Token':row['Token']}
            if row['Token'] == 0:
                time.sleep(0.5)
                start_time = time.time()
                radio.listen = False
                radio.open_tx_pipe(row['Address'])
                token_passed = False
                timed_out = False
                logging.info("Attempting to pass token to node link address: %s",row['Address'])
                while (not token_passed and not timed_out):
                    token_passed = radio.write(TOKEN_PACKET)
                    timed_out = (time.time() - start_time > TIMEOUT_TOKEN)
                if token_passed:
                    logging.info("I successfuly passed the token to node link address: %s", row['Address'])
                    #tb.loc[index,'Token'] = 1
                    new_row['Token'] = 1
                    tb = tb.drop(index)
                    tb = pd.concat([tb, pd.DataFrame(new_row, index=[0])], ignore_index=True)
                    break
        
    if not token_passed:
        logging.info("I couldn't give the token to anyone that didn't had it. Going to try to give it to someone that already had it, in case they can reach other nodes.")
        for index, row in tb.iterrows():
            new_row = {'Address':row['Address'], 'File': row['File'], 'Token':row['Token']}
            if row['Token'] == 1:
                time.sleep(0.5)
                start_time = time.time()
                radio.listen = False
                radio.open_tx_pipe(row['Address'])
                token_passed = False
                timed_out = False
                logging.info("Attempting to pass token to node link address (this node already had the token): %s",row['Address'])
                while (not token_passed and not timed_out):
                    token_passed = radio.write(TOKEN_PACKET)
                    timed_out = (time.time() - start_time > TIMEOUT_TOKEN)
                if token_passed:
                    logging.info("I successfuly passed the token to node link address (this node already had the token): %s", row['Address'])
                    tb =tb.drop(index)
                    tb = pd.concat([tb, pd.DataFrame(new_row, index=[0])], ignore_index=True)
                    break

    logging.debug('token passed:'+str(token_passed))
    logging.info('\n\t' + tb.to_string().replace('\n', '\n\t'))
    
    return token_passed


def receiver():
    """
    Loop until receives a message.
    Take first byte (Header) and identify the message type.
    Call the corresponding function.
    """
    radio = initializeRadio()
    radio.payload_size = 32
    radio.channel = 26 #6A 20
    radio.data_rate = rf24.RF24_250KBPS

    radio.set_pa_level(rf24.rf24_pa_dbm_e.RF24_PA_LOW)
    radio.dynamic_payloads = True
    radio.set_auto_ack(True)
    radio.ack_payloads = False

    radio.set_retries(5,15) 
    radio.open_rx_pipe(1, OWN_ADDRESS) 
    radio.listen = True

    while True:
        while not radio.available():
            time.sleep(1/1000)
            continue
        
        received_message = radio.read(radio.get_dynamic_payload_size())
        logging.info("I received a message!")
        header = received_message[0].to_bytes(1, byteorder='big') 

        if header == HEADER_STATUS:
            logging.info("The received message is an status query")
            receiveStatus(radio, received_message)
        elif header == HEADER_FILE_PACKET:
            logging.info("The received message is a file message")
            receiveFile(radio, received_message)
        elif header == TOKEN_PACKET:
            logging.info("The received message is a Token message.")
            receiveToken(radio)

def receiveStatus(radio, message):
    """
    Open Tx pipe with transmitter address
    Build packet using the token and file global variables.
    Send it back to transmitter (timeout=5-10s)
    """
    time.sleep(0.5)
    radio.listen = False
    tx_address = message[1:6]
    radio.open_tx_pipe(tx_address)
    
    file_info = file.to_bytes(1, byteorder = 'big')
    token_info = token.to_bytes(1, byteorder='big')
    info = HEADER_STATUS_PACKET_REPLY + file_info + token_info
    response = False
    timed_out = False
    start_time = time.time()
    while not response and not timed_out:
        response = radio.write(info)
        timed_out = (time.time() - start_time > TIMEOUT_STATUS)
    radio.listen = True
    time.sleep(0.5)

    logging.debug('timed_out (at receiveStatus):'+ str(timed_out))
    logging.debug('response (at receiveStatus):' + str(response))

def receiveFile(radio, first_message):
    """
    Loop to receive file until an end of transmission is received (or timeout)
    Save the file to USB
    """
    global file
    last_packet_id = b'\xFF'
    transmission_end = False
    message_list = [first_message[2:]]

    timed_out = False
    start_time = time.time()
    while not transmission_end and not timed_out:
        while not radio.available() and not timed_out:
            time.sleep(1/1000)
            timed_out = (time.time() - start_time > TIMEOUT_STATUS)
        if radio.available():
            received_message = radio.read(radio.get_dynamic_payload_size())
            header = received_message[0]
            if header.to_bytes(1, byteorder='big') == HEADER_FILE_PACKET:
                if last_packet_id != received_message[1]:
                    if received_message[2:] == EOT_BYTES:
                        transmission_end = True
                    else:
                        message_list.append(received_message[2:])
                    last_packet_id=received_message[1]
    
    if transmission_end:
        file_data = b''.join(message_list)
        file = 1
        saveFile(file_data)
        logging.debug('File received.')
        #logging.debug(file_data)


def receiveToken(radio):
    """
    When token packet is received. 
    Update token variable
    Then start transmitting mode (send status,...)
    """
    del radio
    time.sleep(0.5)
    logging.debug('Token received. Switching to transmitter mode.')
    transmitter()
