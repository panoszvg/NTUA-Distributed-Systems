from flask import Blueprint, jsonify, request
from node import Node
from blockchain import Blockchain
from config import DEBUG, bootstrap_ip
import config, copy, jsonpickle, time, _thread

node = Node(bootstrap_ip, 5000, 0)


rest = Blueprint('rest', __name__)
blockchain = Blockchain(config.capacity) 


#.......................................................................................

def client():
    while not node.begin_working:
        pass
    print("\n        NBC Client        \n")
    while(True):        
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

            while node.lock.acquire(blocking=False):
                pass

            # validate amount
            temp = node.get_transaction_inputs(amount)
            if temp == None:
                print("Wallet doesn't have sufficient funds to make this transaction")
                print("Wallet: " + str(node.get_wallet_balance(node.id)) + " NBC")
                print()
                if node.lock.locked():
                    node.lock.release()
                continue

            inputs, inputs_sum = temp

            # create transaction
            new_transaction = node.create_transaction(
                receiver_ip=recipient_address.split(":")[0],
                receiver_port=int(recipient_address.split(":")[1]),
                amount=amount,
                inputs=inputs,
                inputs_sum=inputs_sum
            )
            node.pending_transactions.append(new_transaction)
            if node.lock.locked():
                node.lock.release()
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
    while not node.begin_working:
        pass

    node.simulation_start_time = time.time()
    file = open("transactions/" + str(config.nodes) + "nodes/transactions" + str(node.id) + ".txt", "r")
    for line in file:
        if node.mining:
            if DEBUG:
                print("Sim-mining")
        while node.mining:
            pass
        id, amount = line.split(" ")
        id = int(id[-1])
        amount = int(amount)

        if DEBUG:
            print("id: " + str(id) + "  --> IP: " + str(node.ring[id]['ip']) + "  --> Port: " + str(node.ring[id]['port']))
            print("amount: " + str(amount))
            print()
            print("Before acquiring lock in simulation")

        while not((len(node.pending_transactions) < config.capacity) and (node.lock.acquire(blocking=False))):
            pass

        if DEBUG:
            print("Acquired lock in simulation")
        temp = node.get_transaction_inputs(amount)
        if temp == None:
            if DEBUG:
                print("Wallet doesn't have sufficient funds to make this transaction")
                print("Wallet: " + str(node.get_wallet_balance(node.id, True)) + " NBC")
                print()
            if node.lock.locked():
                node.lock.release()
            continue
        
        inputs, inputs_sum = temp

        # create transaction
        new_transaction = node.create_transaction(
            receiver_ip=str(node.ring[id]['ip']),
            receiver_port=node.ring[id]['port'],
            amount=amount,
            inputs=inputs,
            inputs_sum=inputs_sum
        )
        node.pending_transactions.append(new_transaction)

        if node.lock.locked():
            node.lock.release()
    client()



'''
After mining process, when a block is found, it is sent to this endpoint
'''
@rest.route('/block/add', methods=['POST'])
def add_block():
    if DEBUG:
        print("Received a block with txns:")
    block_received = jsonpickle.decode(request.json['block'])
    if DEBUG:
        for transaction in block_received.transactions:
            sender_id = None
            receiver_id = None
            for item in node.ring:
                if item["public_key"] == transaction.sender_address:
                    sender_id = item["id"]
                if item["public_key"] == transaction.receiver_address:
                    receiver_id = item["id"]
            print("Sender: " + str(sender_id) + ", Receiver: " + str(receiver_id) + ", amount: " + str(transaction.amount))
            for t_input in transaction.transaction_inputs:
                print("\tInput: { Owner: " + str(t_input.owner) + ", Amount: " + str(t_input.amount) + " }")
            for t_output in transaction.transaction_outputs:
                print("\tOutput: { Recipient: " + str(t_output.recipient) + ", Amount: " + str(t_output.amount) + " }")
        print()
        print("Incoming block with hash: " + str(block_received.current_hash))
        print("Prev: " + str(block_received.previous_hash))
        print("Curr: " + str(node.chain.blocks[-1].current_hash))
    while node.received_block:
        pass
    node.received_block = True
    correct_block = node.validate_block(block_received)
    if correct_block:
        node.block_received = block_received
    else:
        node.received_block = False
        if not node.resolving_conflicts:
            node.resolving_conflicts = True
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


'''
Get balance of current node [unused by client, can be used in Postman]
'''
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
