import copy
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import jsonpickle
import logging

import config
from block import Block
from node import Node
from blockchain import Blockchain
from transaction_io import Transaction_Output
import wallet
from transaction import Transaction
import wallet
import _thread
import time

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
CORS(app)
blockchain = Blockchain(config.capacity) 


#.......................................................................................

def client():
    print("\n        NBC Client        \n")
    while(True):        
        if node.mining:
            while node.mining:
                pass
        print(">", end=" ")
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
            inputs, inputs_sum = node.get_transaction_inputs(amount)
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
                inputs=inputs,
                inputs_sum=inputs_sum
            )
            node.validate_transaction(new_transaction)
            node.broadcast_transaction(new_transaction)
            print()

        elif cli_input == "view":
            print("View requested")
            transactions = node.view_transactions()
            print(transactions)
            print()
        elif cli_input == "balance":
            print("Balance requested")
            print("Wallet: " + str(node.get_wallet_balance(node.id)) + " NBC")
            print()
        elif cli_input == "chain":
            print("Chain hashes requested")
            for block in node.chain.blocks:
                print("Idx: " + str(block.index) +", Hash: " + str(block.current_hash))
            print()
        else:
            if cli_input != "help":
                print("Command not recognized")
            print("\nAvailable Commands:")
            print("t <recipient_address> <amount>: Create new transaction.")
            print("view:                           View transactions in last block.")
            print("balance:                        Show balance of wallet.")
            print("chain:                          Show validated blocks' ids and hashes.")
            print("help:                           Show available commands.\n\n")


def simulation():
    while node.current_id_count != config.nodes:
        pass
    print("----> " + str(node.current_id_count))

    while not (node.get_wallet_balance(0) == 100 \
    and node.get_wallet_balance(1) == 100 \
    and node.get_wallet_balance(2) == 100 \
    and node.get_wallet_balance(3) == 100 \
    and node.get_wallet_balance(4) == 100):
        print(str(node.get_wallet_balance(0)) + " " + str(node.get_wallet_balance(1)) + " " + str(node.get_wallet_balance(2)) + " " + str(node.get_wallet_balance(3)) + " " + str(node.get_wallet_balance(4)))

    print("All wallets have 100 NBCs")
    print(str(node.get_wallet_balance(0)) + " " + str(node.get_wallet_balance(1)) + " " + str(node.get_wallet_balance(2)) + " " + str(node.get_wallet_balance(3)) + " " + str(node.get_wallet_balance(4)))

    file = open("transactions/5nodes/transactions" + str(node.id) + ".txt", "r")
    for line in file:
        while node.mining:
            pass
        id, amount = line.split(" ")
        id = int(id[-1])
        amount = int(amount)

        print("id: " + str(id) + "  --> IP: " + str(node.ring[id]['ip']) + "  --> Port: " + str(node.ring[id]['port']))
        print("amount: " + str(amount))
        print()

        temp = node.get_transaction_inputs(amount)
        if temp == None:
            print("Wallet doesn't have sufficient funds to make this transaction")
            print("Wallet: " + str(node.get_wallet_balance(node.id)) + " NBC")
            print()
            continue
        
        inputs, inputs_sum = temp

        # create transaction
        new_transaction = node.create_transaction(
            sender_ip=node.ip,
            sender_port=node.port,
            receiver_ip=str(node.ring[id]['ip']),
            receiver_port=node.ring[id]['port'],
            amount=amount,
            signature=node.wallet.private_key,
            inputs=inputs,
            inputs_sum=inputs_sum
        )
        node.validate_transaction(new_transaction)
        node.broadcast_transaction(new_transaction)
    print("Done")


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
        time.sleep(1)
        if config.simulation:
            _thread.start_new_thread(simulation, ())
        else:
            _thread.start_new_thread(client, ())
    
    response = {'id': node.current_id_count - 1}
    return response, 200

@app.route('/block/add', methods=['POST'])
def add_block():
    node.block_received = True
    block_received = jsonpickle.decode(request.json['block'])
    correct_block = node.validate_block(block_received)
    if correct_block:
        node.chain.blocks.append(block_received)
        node.current_block = Block(block_received.current_hash, block_received.index + 1)
    else:
        _thread.start_new_thread(node.resolve_conflicts, ())
    return "OK", 200

'''
When a transaction is created and broadcasted, it will be received in this endpoint
'''
@app.route('/transaction/receive', methods=['POST'])
def receive_transaction():
    transaction = request.json['transaction']
    transaction = jsonpickle.decode(transaction)
    valid_transaction = node.validate_transaction(transaction)
    if valid_transaction:
        node.add_transaction_to_block(transaction)
    return "OK", 200

'''
Get all transactions that have been added to blockchain
'''
@app.route('/transactions/get', methods=['GET'])
def get_transactions():
    transactions = blockchain.get_transactions()
    response = {'transactions': jsonpickle.encode(transactions)}
    return jsonify(response), 200


@app.route('/chain/get', methods=['GET'])
def get_chain():
    response = {'chain': jsonpickle.encode(copy.deepcopy(node.chain)), 'UTXO': jsonpickle.encode(copy.deepcopy(node.UTXOs))}
    return jsonify(response)


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
    genesis = Block(1, 0)
    first_txn = Transaction(node.wallet.public_key, node.wallet.public_key, 100 * config.nodes, [])
    first_txn_output = Transaction_Output(first_txn.transaction_id, 0, first_txn.amount)
    node.UTXOs[0].append(first_txn_output)
    genesis.add_transaction(first_txn)
    genesis.current_hash = genesis.myHash()
    blockchain.add_block(genesis)
    node.current_block = node.create_new_block(1, 1)

    app.run(host='127.0.0.1', port=port)