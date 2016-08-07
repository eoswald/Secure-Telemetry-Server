from flask import Flask, render_template
from flask_socketio import SocketIO, send, emit
from gevent import monkey
monkey.patch_all()
import Queue
import threading
import time
import ssl
import os
import sys

import serial_device as serial
import fakeserial

# Suppress errors in order to ignore the SSLEOFError until we find a fix
# WARNING: THIS IS BAD. Comment it out in order to see the errors.
#f = open(os.devnull, 'w')
#sys.stderr = f


# Serial input queue
serial_queue = Queue.Queue()

# Toggle on if testing
TESTING = True
if TESTING:
    # A fake "Arduino" serial for testing purposes
    arduino_serial = fakeserial.Serial(serial_queue)
else:
    arduino_serial = serial.Serial(serial_queue)

# Flask configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'q-7g{D3(^T!t]e/y'

# SocketIO configuration
socketio = SocketIO(app, async_mode="gevent")

# We should keep track of our clients and only serve data once
serving_data = False
clients = 0

# Function that reads data from our serial input in a separate thread
def serve_data():
    global serving_data
    while serving_data:
        reading = serial_queue.get()
        with app.test_request_context('/'):
            data_dict = dict((field, getattr(reading, field)) for field, _ in reading._fields_)
            socketio.emit('sensor_data', data_dict)
            print("SEND TO CLIENT:", data_dict)
        time.sleep(2)
    thread.exit() # We want the thread to exit once the client disconnected

# Default behavior on accessing the server
@app.route('/')
def index():
    return render_template("data.html")

# For testing/debugging purposes
@app.route('/test')
def test():
    return render_template("RadialprogressTest.html")

# Triggered when a client connects to the server
@socketio.on('connect')
def handle_connect_event():
    global serving_data
    global clients
    clients += 1
    print('LOG: Client connected. Total: ' + str(clients))
    time.sleep(2) # We need to give our thread enough time to exit. Otherwise, a page refresh keeps starting new threads.
    if not serving_data:
        serving_data = True
        arduino_thread = threading.Thread(target=arduino_serial.read, name='Arduino-Read-Thread')
        data_thread = threading.Thread(target=serve_data, name='Data-Server-Thread')
        arduino_thread.start()
        data_thread.start()


# Triggered when a client disconnects from the server
@socketio.on('disconnect')
def handle_disconnect_event():
    global serving_data
    global clients
    clients -= 1
    print('LOG: Client disconnected. Total: ' + str(clients))
    if clients == 0:
        serving_data = False

# Triggered when the client sends the braking signal
@socketio.on('brake')
def handle_brake_event(message):
    if message["type"] == 'emergency':
        arduino_serial.write("Brake now!")

if __name__ == '__main__':
    # TODO: Current certificate and key are for testing purposes only
    socketio.run(app, host='127.0.0.1', port=8443, 
                        certfile='ssl/server/server.cer', keyfile='ssl/server/server.key', 
                        ca_certs='ssl/server/ca.cer', 
                        cert_reqs=ssl.CERT_REQUIRED,
                        ssl_version=ssl.PROTOCOL_TLSv1_2) 

    while True:
        time.sleep(1)

