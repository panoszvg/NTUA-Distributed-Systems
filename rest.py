import json
from re import L
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
import _thread
import time


app = Flask(__name__)
CORS(app)
blockchain = Blockchain(config.capacity)


#.......................................................................................

def client():
    time.sleep(2) # give enough time for nodes to be initialized
    print("\n        NBC Client        \n")
    while(True):
        cli_input = input()
        if cli_input[0:2] == "t ":
            print("New transaction requested")
        elif cli_input == "view":
            print("View requested")
            transactions = node.view_transactions()
            print(transactions)
            print()
        elif cli_input == "balance":
            print("Balance requested")
            print("Wallet has " + str(node.get_wallet_balance(node.id)) + " NBC")
            print()
        else:
            if cli_input != "help":
                print("Command not recognized")
            print("\nAvailable Commands:")
            print("t <recipient_address> <amount>: Create new transaction.")
            print("view:                           View transactions in last block.")
            print("balance:                        Show balance of wallet.")
            print("help:                           Show available commands.\n\n")

'''
When all nodes are inserted, bootstrap will use this endpoint to broadcast the ring
'''
@app.route('/node/initialize', methods=['POST'])
def receive_ring():
    node.ring = request.json['ring']
    node.chain = jsonpickle.decode(request.json['chain']) # validate before adding
    node.UTXOs = jsonpickle.decode(request.json['UTXOs'])
    _thread.start_new_thread(client, ())
    return "OK", 200


@app.route('/block/add', methods=['POST'])
def add_block():
    block_received = jsonpickle.decode(request.json['block'])
    correct_block = node.validate_block(block_received)
    if correct_block:
        node.chain.blocks[-1] = block_received
    else:
        print("Problem: must validate chain")
    return "OK", 200


'''
When a transaction is created and broadcasted, it will be received in this endpoint
'''
@app.route('/transaction/receive', methods=['POST'])
def receive_transaction():
    transaction = request.json['transaction']
    transaction = jsonpickle.decode(transaction)
    # print("UTXOs so far:")
    # for user in node.UTXOs:
    #     for utxo in user:
    #         print(utxo.to_dict())
    # print("\n\n\n")
    valid_transaction = node.validate_transaction(transaction)
    if valid_transaction:
        node.add_transaction_to_block(transaction)
    # print("UTXOs after transaction:")
    # for user in node.UTXOs:
    #     for utxo in user:
    #         print(utxo.to_dict())
    # print("\n\n\n")
    return "OK", 200


'''
Get all transactions that have been added to blockchain
'''
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
    node = Node('127.0.0.1', port, 0)
    data = {
        'ip': '127.0.0.1',
        'port': port,
        'public_key': node.wallet.public_key
    }
    req = requests.post('http://localhost:5000/node/register', json=data)
    if (not req.status_code == 200):
        print("Problem")
        exit(1)

    node.id = json.loads(req.content.decode())['id']
    node.current_id_count = node.id + 1

    app.run(host='127.0.0.1', port=port)