from flask import Flask, request
from flask_cors import CORS
from block import Block
from blockchain import Blockchain
from transaction_io import Transaction_Output
from transaction import Transaction
import config, logging, time, _thread
from common_functions import *



app = Flask(__name__)
app.register_blueprint(rest)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
CORS(app)
blockchain = Blockchain(config.capacity) 


#.......................................................................................

'''
When a node wants to be registered and get an id, it will use this endpoint
'''
@app.route('/node/register', methods=['POST'])
def register_node():
    node_data = request.json
    node.register_node_to_ring(
        id=node.current_id_count,
        ip=node_data['ip'],
        port=node_data['port'],
        public_key=jsonpickle.decode(node_data['public_key'])
    )
    if node.current_id_count == config.nodes:
        _thread.start_new_thread(node.initialize_nodes, ())
        time.sleep(1)
        _thread.start_new_thread(node.worker, ())
        if config.simulation:
            _thread.start_new_thread(simulation, ())
        else:
            _thread.start_new_thread(client, ())
    
    response = {'id': node.current_id_count - 1}
    return response, 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    node.register_node_to_ring(node.id, node.ip, node.port, node.wallet.public_key)
    blockchain = node.chain
    genesis = Block(1, 0)
    first_txn = Transaction(node.wallet.public_key, node.wallet.public_key, 100 * config.nodes, [])
    first_txn_output = Transaction_Output(first_txn.transaction_id, 0, first_txn.amount)
    node.UTXOs[0].append(first_txn_output)
    genesis.add_transaction(first_txn)
    genesis.current_hash = genesis.myHash()
    blockchain.add_block(genesis)
    node.current_block = node.create_new_block(1, 1)

    app.run(host=config.bootstrap_ip, port=port)