from flask import Flask, request
from flask_cors import CORS
from blockchain import Blockchain
import config, json, jsonpickle, logging, requests, _thread, os
from common_functions import *


app = Flask(__name__)
app.register_blueprint(rest)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
CORS(app)
blockchain = Blockchain(config.capacity)


#.......................................................................................

'''
When all nodes are inserted, bootstrap will use this endpoint to broadcast the ring
'''
@app.route('/node/initialize', methods=['POST'])
def receive_ring():
    if DEBUG:
        print("Received ring")
    node.ring = jsonpickle.decode(request.json['ring'])
    valid_chain = node.validate_chain(jsonpickle.decode(request.json['chain']))
    _thread.start_new_thread(node.worker, ())
    if valid_chain: 
        node.chain = jsonpickle.decode(request.json['chain'])
        node.current_block = jsonpickle.decode(request.json['current_block'])
    else:
        print("Problem")
        exit(1)
    node.UTXOs = jsonpickle.decode(request.json['UTXOs'])
    # copy UTXOs to pending_UTXOs
    for utxo in node.UTXOs:
        node.pending_UTXOs.append(copy.deepcopy(utxo))
    node.current_id_count = len(node.UTXOs)
    # node.begin_working = True
    if config.simulation:
        _thread.start_new_thread(simulation, ())
    else:
        _thread.start_new_thread(client, ())
    return "OK", 200


@app.route('/begin', methods=['POST'])
def begin():
    node.begin_working = True
    return "OK", 200


# run it once for every node

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    node.port = port
    ipv4 = os.popen('ip addr show eth1 | grep "\<inet\>" | awk \'{ print $2 }\' | awk -F "/" \'{ print $1 }\'').read().strip()
    data = {
        'ip': ipv4,
        'port': port,
        'public_key': jsonpickle.encode(node.wallet.public_key)
    }
    req = requests.post('http://' + config.bootstrap_ip + ':5000/node/register', json=data)
    if (not req.status_code == 200):
        print("Problem")
        exit(1)

    node.id = json.loads(req.content.decode())['id']
    node.current_id_count = node.id + 1

    app.run(host=ipv4, port=port)