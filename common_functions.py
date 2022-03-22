from flask import Blueprint, jsonify, request
from block import Block
from node import Node
from blockchain import Blockchain
from config import DEBUG, bootstrap_ip
import config, copy, jsonpickle, time, _thread

node = Node(bootstrap_ip, 5000, 0)


rest = Blueprint('rest', __name__)
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
                receiver_ip=recipient_address.split(":")[0],
                receiver_port=int(recipient_address.split(":")[1]),
                amount=amount,
                signature=node.wallet.private_key,
                inputs=inputs,
                inputs_sum=inputs_sum
            )
            valid_transaction = node.validate_transaction(new_transaction)
            if valid_transaction:
                node.add_transaction_to_block(new_transaction)
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
        elif cli_input == "balances":
            print("Balances requested")
            for i in range(0, config.nodes):
                print("Wallet: " + str(node.get_wallet_balance(i)) + " NBC")
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
            print("balances:                       Show balances of all wallets.")
            print("chain:                          Show validated blocks' ids and hashes.")
            print("help:                           Show available commands.\n\n")


def simulation():
    while node.current_id_count != config.nodes:
        pass

    while not (node.get_wallet_balance(0) == 100 \
    and node.get_wallet_balance(1) == 100 \
    and node.get_wallet_balance(2) == 100 \
    and node.get_wallet_balance(3) == 100 \
    and node.get_wallet_balance(4) == 100):
        pass

    if DEBUG:
        print("All wallets have 100 NBCs")
        print(str(node.get_wallet_balance(0)) + " " + str(node.get_wallet_balance(1)) + " " + str(node.get_wallet_balance(2)) + " " + str(node.get_wallet_balance(3)) + " " + str(node.get_wallet_balance(4)))

    timestamp_1 = time.time()

    file = open("transactions/" + str(config.nodes) + "nodes/transactions" + str(node.id) + ".txt", "r")
    for line in file:
        while node.mining:
            pass
        id, amount = line.split(" ")
        id = int(id[-1])
        amount = int(amount)

        if DEBUG:
            print("id: " + str(id) + "  --> IP: " + str(node.ring[id]['ip']) + "  --> Port: " + str(node.ring[id]['port']))
            print("amount: " + str(amount))
            print()
			
        while not node.lock.acquire(blocking=False):
            pass

        if DEBUG:
            print("Before acquiring lock in simulation")
            print("Acquired lock in simulation")
        temp = node.get_transaction_inputs(amount)
        if temp == None:
            if DEBUG:
                print("Wallet doesn't have sufficient funds to make this transaction")
                print("Wallet: " + str(node.get_wallet_balance(node.id)) + " NBC")
                print()
            if node.lock.locked():
                node.lock.release()
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
        valid_transaction = node.validate_transaction(new_transaction)
        if node.lock.locked():
            node.lock.release()
        if valid_transaction:
            node.add_transaction_to_block(new_transaction)
            node.broadcast_transaction(new_transaction)
    print("Simulation is done")
    timestamp_2 = time.time()
    print("Time spent in simulation: " + str(timestamp_2 - timestamp_1) + " sec.")
    client()



'''
After mining process, when a block is found, it is sent to this endpoint
'''
@rest.route('/block/add', methods=['POST'])
def add_block():
    node.block_received = True
    block_received = jsonpickle.decode(request.json['block'])
    correct_block = node.validate_block(block_received)
    if correct_block:
        node.chain.blocks.append(block_received)
        node.current_block = Block(block_received.current_hash, block_received.index + 1)
    else:
        if config.scalable:
            _thread.start_new_thread(node.resolve_conflicts_scalable, ())
        else:
            _thread.start_new_thread(node.resolve_conflicts, ())
    return "OK", 200


'''
When a transaction is created and broadcasted, it will be received in this endpoint
'''
@rest.route('/transaction/receive', methods=['POST'])
def receive_transaction():
    transaction = request.json['transaction']
    transaction = jsonpickle.decode(transaction)
    node.pending_transactions.append(transaction)
    return "OK", 200

'''
Get all transactions that have been added to blockchain
'''
@rest.route('/transactions/get', methods=['GET'])
def get_transactions():
    transactions = blockchain.get_transactions()
    response = {'transactions': jsonpickle.encode(transactions)}
    return jsonify(response), 200




@rest.route('/balance', methods=['GET'])
def balance():
    balance = node.get_wallet_balance()
    response = {'balance': jsonpickle.encode(balance)}
    return jsonify(response), 200

'''
Endpoint used when resolving conflicts, give chain (and other info) to update node that asks for it
'''
@rest.route('/chain/get', methods=['GET'])
def get_chain():
    response = {
        'chain': jsonpickle.encode(copy.deepcopy(node.chain)),
        'current_block': jsonpickle.encode(node.current_block)
    }
    return jsonify(response), 200

'''
Endpoint used when resolving conflicts (optimised), give chain length and hashes
'''
@rest.route('/chain/length', methods=['GET'])
def get_chain_length():
    chain_hashes = []
    for block in node.chain.blocks:
        chain_hashes.append(block.current_hash)
    response = {
        'chain': jsonpickle.encode(copy.deepcopy(chain_hashes)),
        'length': jsonpickle.encode(len(node.chain.blocks))
    }
    return jsonify(response)

'''
Endpoint used when resolving conflicts, give chain (and other info) to update node that asks for it
'''
@rest.route('/chain/get/<blocks>', methods=['GET'])
def get_chain_last(blocks):
    response = {
        'blocks': jsonpickle.encode(copy.deepcopy(node.chain.blocks[-int(blocks):])),
        'current_block': jsonpickle.encode(node.current_block)
    }
    return jsonify(response), 200