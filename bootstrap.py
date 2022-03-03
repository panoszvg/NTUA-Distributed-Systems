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

            # split string to arguments
            cli_input = cli_input[2:].split()
            if len(cli_input) != 2:
                print("Arguments given must be 2: <recipient_address> <amount>\n")
                continue

            # validate first argument
            recipient_address = cli_input[0]
            flag = False
            for n in node.ring:
                if n['id'] == node.id: # skip self
                    continue
                if n['ip'] + ":" + str(n['port']) == recipient_address:
                    flag = True
            if not flag:
                print("'" + recipient_address + "' is not valid address.\n")
                continue
            
            # validate second argument
            try:
                int(cli_input[1])
            except:
                print("'" + cli_input + " can't be converted to an integer.")
                continue
            amount = int(cli_input[1])

            # validate amount
            inputs = node.get_transaction_inputs(amount)
            if inputs == None:
                print("Wallet doesn't have sufficient funds to make this transaction")
                print("Wallet: " + str(node.get_wallet_balance(node.id)) + " NBC")
                print()
                continue

            # create transaction
            new_transaction = node.create_transaction(
                sender_ip=node.ip,
                sender_port=node.port,
                receiver_ip=recipient_address.split(":")[0],
                receiver_port=int(recipient_address.split(":")[1]),
                amount=amount,
                signature=node.wallet.private_key,
                inputs=inputs
            )
            node.validate_transaction(new_transaction)
            node.broadcast_transaction(new_transaction)

        elif cli_input == "view":
            print("View requested")
            transactions = node.view_transactions()
            print(transactions)
            print()
        elif cli_input == "balance":
            print("Balance requested")
            print("Wallet: " + str(node.get_wallet_balance(node.id)) + " NBC")
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
When a node wants to be registered and get an id, it will use this endpoint
'''
@app.route('/node/register', methods=['POST'])
def register_node():
    node_data = request.json
    node.register_node_to_ring(
        id=node.current_id_count,
        ip=node_data['ip'],
        port=node_data['port'],
        public_key=node_data['public_key']
    )
    if node.current_id_count == config.nodes:
        _thread.start_new_thread(node.initialize_nodes, ())
        _thread.start_new_thread(client, ())
    
    response = {'id': node.current_id_count - 1}
    return response, 200

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

'''
Get the entire blockchain
'''
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
    node = Node(boostrap_ip, port, 0)
    node.register_node_to_ring(node.id, node.ip, node.port, node.wallet.public_key)
    blockchain = node.chain
    genesis = block.Block(1, 0)
    first_txn = Transaction(node.wallet.public_key, node.wallet.public_key, 100 * config.nodes, [])
    first_txn_output = Transaction_Output(first_txn.transaction_id, 0, first_txn.amount)
    node.UTXOs[0].append(first_txn_output)
    genesis.add_transaction(first_txn)
    blockchain.add_block(genesis)

    app.run(host='127.0.0.1', port=port)