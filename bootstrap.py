import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import jsonpickle

import config
import block
from node import Node
from blockchain import Blockchain
from transaction_io import Transaction_Output
import wallet
from transaction import Transaction
import wallet

app = Flask(__name__)
CORS(app)
blockchain = Blockchain(config.capacity)


#.......................................................................................

@app.route('/node/register', methods=['POST'])
def register_node():
    node_data = request.json
    node.register_node_to_ring(
        ip=node_data['ip'],
        port=node_data['port'],
        public_key=node_data['public_key'],
        amount=node_data['amount']
    )
    if Node.current_id_count == 2:
        node.initialize_nodes()
    
    return "OK", 200



# get all transactions in the blockchain

@app.route('/transactions/get', methods=['GET'])
def get_transactions():
    transactions = blockchain.get_transactions()
    for txn in transactions:
        txn = txn.to_dict()
        print()
        print(txn)
        print()
    print(type(transactions))
    print(type(transactions[0].to_dict()))

    response = {'transactions': jsonpickle.encode(transactions)}
    print(response)
    return jsonify(response), 200


# get blockchain

@app.route('/blockchain', methods=['GET'])
def get_blockchain():
    response = {'blockchain': jsonpickle.encode(blockchain.blocks)}
    print(response)
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    boostrap_ip = '127.0.0.1'
    node = Node(boostrap_ip, port)
    node.id = 0
    Node.current_id_count += 1
    blockchain = node.chain
    genesis = block.Block(1, 0)
    first_txn = Transaction(node.wallet.public_key, node.wallet.public_key, 100 * config.nodes, [])
    genesis.add_transaction(first_txn)
    blockchain.add_block(genesis)

    app.run(host='127.0.0.1', port=port)