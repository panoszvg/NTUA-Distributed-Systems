import json
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS


import block
from node import Node
from blockchain import Blockchain
import wallet
import transaction
import wallet
import jsonpickle
import config



app = Flask(__name__)
CORS(app)
blockchain = Blockchain(config.capacity)


#.......................................................................................

@app.route('/transaction/receive', methods=['POST'])
def receive_transaction():
    test = 0
    node_data = request.json



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



# run it once for every node

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    node = Node('127.0.0.1', port)
    data = {
        'ip': '127.0.0.1',
        'port': port,
        'public_key': node.wallet.public_key,
        'amount': 0
    }
    req = requests.post('http://localhost:5000/node/register', json=data)
    if (not req.status_code == 200):
        print("Problem")
        exit(1)

    app.run(host='127.0.0.1', port=port)