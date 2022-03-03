import datetime
import json
from socketserver import ThreadingUnixDatagramServer
import time
from ipaddress import ip_address
from random import randint
from Crypto.Hash import SHA256
import jsonpickle
from numpy import broadcast
from block import Block
from blockchain import Blockchain
from transaction import Transaction
from transaction_io import Transaction_Input, Transaction_Output
from wallet import Wallet
import requests
import config
import _thread

class Node:

	'''
	Initialize a node in the network

	Attributes
	----------
	wallet: Wallet
		the Wallet object of this node
	ring: list of dict
		here we store information for every node, as its id, its address (ip:port) its public key (and its balance - will deprecate)
	chain: Blockchain
		blockchain that exists in this node
	id: int
		number that represents a node (0, ..., n-1)
	current_id_count: int
		how many nodes exist - basically size of ring
	UTXOs: list of list of Transaction_Output
		list of UTXOs for each node
	'''
	def __init__(self, ip, port, id):
		self.chain = Blockchain(config.capacity)
		self.id = id
		self.current_id_count = id # will be updated in main
		self.UTXOs = []
		self.wallet = self.generate_wallet()
		self.ip = ip
		self.port = port
		self.ring = []

	'''
	Get balance of a wallet in a node by adding its UTXOs
	that exist in current node (every node is always up to date)

	Parameters:
	-----------
	id: int
		the id of the node in order to search UTXOs (list of list of Transaction_Output)
	'''
	def get_wallet_balance(self, id):
		sum = 0
		for utxo in self.UTXOs[id]:
			sum += utxo.amount
		return sum

	'''
	Get transactions that exist in the last block
	'''
	def view_transactions(self):
		transactions_obj = self.chain.blocks[-1].transactions
		transactions = []
		for transaction in transactions_obj:
			transactions.append(transaction.to_dict())
		return transactions

	'''
	Get list of Transaction_Input that is needed for a transaction

	Parameters:
	-----------
	amount: int
		the amount of NBC requested to be found in UTXOs
	
	return: list of Transaction_Input | None
		if there are enough funds for the transaction, will return list of 
		Transaction_Input, otherwise will return None
	'''
	def get_transaction_inputs(self, amount):
		balance = self.get_wallet_balance(self.id)
		if balance >= amount:
			sum = 0
			inputs = [] # list of Transaction_Input to be used
			for transaction in self.UTXOs[self.id]:
				sum += transaction.amount
				print("Added Transaction_Input with id = " + transaction.id)
				inputs.append(Transaction_Input(transaction.id))
				if sum >= amount:
					return inputs
		else:
			print("Problem")
			return None

	'''
	Creates a new Block object and returns it

	Parameters:
	-----------
	previous_hash: str
		hash of the previous block, needed for validation of chain
	index: int
		index of current block
	'''
	def create_new_block(self, previous_hash, index):
		return Block(previous_hash, index)
		

	'''
	Creates a new wallet, including a new pair of private/public key using RSA.
	Implementation is in constructor of Wallet class in 'wallet.py'
	'''
	def generate_wallet(self):
		return Wallet()


	'''
	Add this node to the ring; only the bootstrap node can add a node to the ring after checking his wallet and ip:port address
	bootstrap node informs all other nodes and gives the request node an id and 100 NBCs
	'''
	def register_node_to_ring(self, id, ip, port, public_key):
		self.ring.append(dict(
			id = id,
			ip = ip,
			port = port,
			public_key = public_key
		))
		self.current_id_count += 1
		self.UTXOs.append([])

	'''
	Method to initialize nodes other than bootstrap, it is called after the other Node objects have been
	created and added to ring variable. This method broadcasts ring to the other nodes and creates initial
	transactions to give other nodes their first 100 NBC.
	'''
	def initialize_nodes(self):
		time.sleep(1) # needed so that final node gets response with id before ring broadcast
		data = { 'ring': self.ring, 'chain': jsonpickle.encode(self.chain), 'UTXOs': jsonpickle.encode(self.UTXOs) }

		for node in self.ring:
			if node['id'] == self.id:
				continue
			url = "http://" + node['ip'] + ":" + str(node['port']) + "/node/initialize"
			req = requests.post(url, json=data)
			if (not req.status_code == 200):
				print("Problem")
				exit(1)

		for node in self.ring:
			if node['id'] == self.id:
				continue
			transaction = self.create_transaction(
				sender_id=self.ring[self.id]['ip'],
				sender_port=self.ring[self.id]['port'],
				receiver_ip=node['ip'],
				receiver_port=node['port'],
				signature=self.wallet.private_key,
				amount=100,
				inputs=self.get_transaction_inputs(100) # no need to check if it returns None, it's always correct
			)
			self.validate_transaction(transaction) # otherwise do manually
			self.broadcast_transaction(transaction)


	'''
	Creates a transaction with Transaction Inputs/Outputs. Don't assume it is correct - and 
	in case it isn't there is an extra check in validate_transaction() (for extra security)

	Parameters:
	-----------
	sender: str
		IP of the node that sends NBC
	receiver: str
		IP of the node that receives NBC
	signature: str
		private key of the sender
	amount: int
		the amount of NBC to be sent
	inputs: list of Transaction_Input
		list that contains previous UTXO ids
	'''
	def create_transaction(self, sender_id, sender_port, receiver_ip, receiver_port, signature, amount, inputs):
		# finder sender's id and balance and make sure it's sufficient
		sender_id = next(item for item in self.ring if item["ip"] == sender_id and item["port"] == sender_port)['id'] # max n iterations
		sender_wallet_NBCs = self.get_wallet_balance(sender_id)
		if sender_wallet_NBCs < amount:
			print("Error: insufficent balance")
			return
		recipient_id = next(item for item in self.ring if item["ip"] == receiver_ip and item["port"] == receiver_port)['id'] # max n iterations
		print("Choose recipient_id = " + str(recipient_id))

		transaction = Transaction(self.ring[sender_id]['public_key'], self.ring[recipient_id]['public_key'], amount, inputs)
		transaction.sign_transaction(signature)
		output_sender = Transaction_Output(
							transaction_id=transaction.transaction_id,
							recipient=sender_id,
							amount=sender_wallet_NBCs - amount
						)
		transaction.transaction_outputs.append(output_sender)

		output_recipient = Transaction_Output(
			transaction_id=transaction.transaction_id,
			recipient=recipient_id,
			amount=amount
		)
		transaction.transaction_outputs.append(output_recipient)
		self.add_transaction_to_block(transaction)
		return transaction


	'''
	Broadcasts a transaction to other nodes

	Parameters:
	-----------
	transaction: Transaction
		transaction to be broadcasted
	'''
	def broadcast_transaction(self, transaction):
		json = { 'transaction': jsonpickle.encode(transaction) }
		for node in self.ring:
			if node['id'] == self.id:
				continue
			requests.post("http://" + node['ip'] + ":" + str(node['port']) + "/transaction/receive", json=json)


	'''
	Validates a transaction's signature, removes UTXOs that are given as inputs
	and adds UTXOs that are given as outputs

	Parameters:
	-----------
	transaction: Transaction
		transaction to be validated
	'''
	def validate_transaction(self, transaction):
		#use of signature and NBCs balance
		# print("Transaction to be validated:")
		# print(transaction.to_dict())
		# print()
		# print("Transaction Inputs to be validated:")
		# for input in transaction.transaction_inputs:
		# 	print(input.to_dict())
		# print()
		# print("Transaction Outputs to be validated:")
		# for input in transaction.transaction_outputs:
		# 	print(input.to_dict())
		# print("\n\n")
		verified = transaction.verify_signature()
		############## also check for sufficient balance
		if verified:
			# find id of sender
			sender_id = next(item for item in self.ring if item["public_key"] == transaction.sender_address)['id'] # max n iterations
			# for that sender, find all UTXOs that correspond to the inputs and delete them
			for input in transaction.transaction_inputs:
				utxo_to_be_deleted = next((x for x in self.UTXOs[sender_id] if x.id == input.previous_output_id), None)
				self.UTXOs[sender_id].remove(utxo_to_be_deleted)
			# add all (both) outputs to UTXOs
			for output in transaction.transaction_outputs:
				node_id = output.recipient
				self.UTXOs[node_id].append(output)
			return True
		else:
			print("Error")
			return False


	'''
	Adds a transaction to the end of the last block and if the block 
	is full, starts mining process
	
	Parameters:
	-----------
	transaction: Transaction
		transaction to be added to block
	'''
	def add_transaction_to_block(self, transaction):
		#if enough transactions mine
		self.chain.blocks[-1].add_transaction(transaction)
		if len(self.chain.blocks[-1].transactions) == self.chain.capacity:
			_thread.start_new_thread(self.mine_block, ())
		return

	'''
	Mines a block: searches for the right nonce, and when it
	finds it, it adds a timestamp and broadcasts the block to the other nodes
	'''
	def mine_block(self):
		nonce = randint(0, 2^32)
		while (True):
			sha_str = SHA256.new(nonce).hexdigest()
			if sha_str.startswith('0' * config.difficulty):
				break

			nonce = (nonce + 1) % (2^32)

		block = self.chain.blocks[-1]
		block.nonce = nonce
		block.current_hash = block.myHash()

		self.broadcast_block(block)


	'''
	Broadcasts a block to the other nodes

	Parameters:
	-----------
	block: Block
		the block with nonce and current_hash defined
	'''
	def broadcast_block(self, block):
		for node in self.ring:
			if node['id'] == self.id:
				continue
			requests.post("http://" + node['ip'] + ":" + node['port'] + "/block/add", json={ 'block' : jsonpickle.encode(block) }) # create endpoint in rest


		
	'''
	Validate the current and previous hash of block received by another node

	Parameters:
	-----------
	block: Block
		the block received
	difficulty: int
		how many 0s the hash must have as a prefix
	'''
	def validate_block(self, block, difficulty=config.difficulty):
		if block.previous_hash == self.chain.blocks[-1].current_hash and block.nonce[0:difficulty] == "0" * difficulty:
			return True
		return False


	# #concensus functions

	# def valid_chain(self, chain):
	# 	#check for the longer chain accroose all nodes


	# def resolve_conflicts(self):
	# 	#resolve correct chain



