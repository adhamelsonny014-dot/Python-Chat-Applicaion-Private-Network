from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes
import socket as py_socket
import threading
import os
import platform
from termcolor import colored
from colorama import init
from datetime import datetime
import logging
from threading import Thread
import time

# Initialize
init()
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, async_mode='threading')

# Global storage for active connections
active_connections = {}

# Constants
PRIME = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
GENERATOR = 2

def generate_dh_key():
    private_key = int.from_bytes(get_random_bytes(32), byteorder='big') % PRIME
    public_key = pow(GENERATOR, private_key, PRIME)
    return private_key, public_key

def derive_shared_key(private_key, peer_public_key):
    shared_secret = pow(peer_public_key, private_key, PRIME)
    return HKDF(shared_secret.to_bytes(256, byteorder='big'), 32, b'', SHA256)

def encrypt_message(key, message):
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_GCM, iv)
    ciphertext, tag = cipher.encrypt_and_digest(message.encode())
    return iv + ciphertext + tag

def decrypt_message(key, encrypted):
    iv = encrypted[:16]
    ciphertext = encrypted[16:-16]
    tag = encrypted[-16:]
    cipher = AES.new(key, AES.MODE_GCM, iv)
    return cipher.decrypt_and_verify(ciphertext, tag).decode()

def listen_for_raw_messages(conn, socketio_sid):
    buffer = b''
    while True:
        try:
            # Read message length (4 bytes)
            while len(buffer) < 4:
                data = conn.recv(4 - len(buffer))
                if not data:
                    raise ConnectionError("Connection closed")
                buffer += data
            
            msg_len = int.from_bytes(buffer[:4], byteorder='big')
            buffer = buffer[4:]
            
            # Read the message content
            while len(buffer) < msg_len:
                data = conn.recv(min(4096, msg_len - len(buffer)))
                if not data:
                    raise ConnectionError("Connection closed")
                buffer += data
            
            encrypted_msg = buffer[:msg_len]
            buffer = buffer[msg_len:]
            
            conn_info = active_connections.get(socketio_sid)
            if not conn_info or not conn_info.get('shared_key'):
                logging.error("No shared key available")
                break
                
            decrypted = decrypt_message(conn_info['shared_key'], encrypted_msg)
            
            socketio.emit('message', {
                'text': decrypted,
                'sender': {'name': 'Client', 'avatar': 'https://i.pravatar.cc/150?img=5'},
                'timestamp': datetime.now().isoformat()
            }, room=socketio_sid)
            
        except ConnectionError as e:
            logging.error(f"Connection error: {e}")
            break
        except Exception as e:
            logging.error(f"Message processing error: {e}")
            break
    
    # Clean up
    cleanup_connection(socketio_sid)

def cleanup_connection(socketio_sid):
    if socketio_sid in active_connections:
        conn = active_connections[socketio_sid].get('conn')
        if conn:
            try:
                conn.close()
            except:
                pass
        del active_connections[socketio_sid]
    
    socketio.emit('status-update', {
        'text': 'Disconnected',
        'class': 'offline'
    }, room=socketio_sid)
    
    socketio.emit('user-disconnected', {
        'name': 'Client'
    }, room=socketio_sid)

def socket_server_thread(ip, port, name, socketio_sid):
    s = py_socket.socket(py_socket.AF_INET, py_socket.SOCK_STREAM)
    if platform.system() == 'Windows':
        s.setsockopt(py_socket.SOL_SOCKET, py_socket.SO_REUSEADDR, 1)
    
    try:
        s.bind((ip, port))
        s.listen(1)
        s.settimeout(30)  # Timeout for accept
        
        logging.info(colored(f"[+] Listening on {ip}:{port}", "yellow"))
        socketio.emit('status-update', {
            'text': 'Waiting for connection...',
            'class': 'offline'
        }, room=socketio_sid)
        
        while True:
            try:
                conn, addr = s.accept()
                logging.info(colored(f"[+] Connection from {addr}", "green"))
                
                # DH Key Exchange
                private_key, public_key = generate_dh_key()
                conn.settimeout(10.0)
                
                # Send our public key
                conn.sendall(f"{public_key},{PRIME},{GENERATOR}\n".encode())
                
                # Receive client's public key
                client_data = b''
                start_time = time.time()
                while True:
                    try:
                        chunk = conn.recv(1)  # Read one byte at a time
                        if not chunk:
                            raise ValueError("Connection closed during key exchange")
                        client_data += chunk
                        if chunk == b'\n':
                            break
                        if time.time() - start_time > 10:  # 10 second timeout
                            raise ValueError("Key exchange timeout")
                    except py_socket.timeout:
                        raise ValueError("Key exchange timeout")
                
                client_public_key = int(client_data.decode().strip())
                shared_key = derive_shared_key(private_key, client_public_key)
                
                # Store connection
                active_connections[socketio_sid] = {
                    'conn': conn,
                    'shared_key': shared_key,
                    'addr': addr
                }
                
                logging.info(colored("[+] Key exchange completed", "green"))
                socketio.emit('status-update', {
                    'text': 'Connected',
                    'class': 'online'
                }, room=socketio_sid)
                
                socketio.emit('user-connected', {
                    'name': 'Client'
                }, room=socketio_sid)
                
                # Start message listener
                Thread(target=listen_for_raw_messages, 
                      args=(conn, socketio_sid),
                      daemon=True).start()
                
                # Reset timeout for normal operation
                conn.settimeout(None)
                break
                
            except py_socket.timeout:
                continue
            except Exception as e:
                logging.error(colored(f"[!] Connection error: {str(e)}", "red"))
                if 'conn' in locals():
                    try:
                        conn.close()
                    except:
                        pass
                continue
                
    except Exception as e:
        logging.error(colored(f"[!] Server error: {str(e)}", "red"))
        socketio.emit('status-update', {
            'text': 'Server error',
            'class': 'offline'
        }, room=socketio_sid)
    finally:
        s.close()

@app.route('/')
def index():
    if 'server_data' not in session:
        return redirect(url_for('server_setup'))
    return render_template('index.html')

@app.route('/server-setup', methods=['GET', 'POST'])
def server_setup():
    if request.method == 'POST':
        session['server_data'] = {
            'name': request.form['name'],
            'ip': request.form['ip'],
            'port': int(request.form['port'])
        }
        return redirect(url_for('index'))
    return render_template('server-setup.html')

@app.route('/get-user-data')
def get_user_data():
    if 'server_data' in session:
        return jsonify({
            'user': {
                'name': session['server_data']['name'],
                'avatar': 'https://i.pravatar.cc/150?img=8'
            },
            'otherUser': {
                'name': 'Anonymous',
                'avatar': 'https://i.pravatar.cc/150?img=5',
                'online': False
            },
            'isServer': True
        })
    return jsonify({'error': 'No session data'}), 400

@socketio.on('connect')
def handle_connect():
    if 'server_data' in session:
        Thread(target=socket_server_thread,
              args=(session['server_data']['ip'],
                    session['server_data']['port'],
                    session['server_data']['name'],
                    request.sid),
              daemon=True).start()

@socketio.on('message')
def handle_message(msg):
    if request.sid not in active_connections:
        emit('error', {'message': 'Not connected'})
        return
    
    try:
        conn_info = active_connections[request.sid]
        shared_key = conn_info['shared_key']
        conn = conn_info['conn']
        
        message = f"{session['server_data']['name']}: {msg['text']}"
        encrypted = encrypt_message(shared_key, message)
        
        # Send message length first
        conn.sendall(len(encrypted).to_bytes(4, byteorder='big'))
        # Then send the message
        conn.sendall(encrypted)
        
    except ConnectionError as e:
        logging.error(f"Connection error while sending: {e}")
        cleanup_connection(request.sid)
        emit('error', {'message': 'Connection lost while sending'})
    except Exception as e:
        logging.error(f"Message sending error: {e}")
        emit('error', {'message': str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    cleanup_connection(request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)