import datetime
import json
import time
from ipaddress import ip_address
from random import randint
from Crypto.Hash import SHA256
from numpy import broadcast
from block import Block
from blockchain import Blockchain
from transaction import Transaction
from transaction_io import Transaction_Output
from wallet import Wallet
import requests
import config

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
	def __init__(self, ip, port, current_node_count):
		self.chain = Blockchain(config.capacity)
		self.id = current_node_count
		self.current_id_count = current_node_count
		if self.id == 0:
			self.UTXOs = []
		else:
			self.UTXOs = [[]]
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
	Creates a new Block object and returns it
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
		ring_data = { 'ring': self.ring }
		print(ring_data)
		for node in self.ring:
			print(node['id'])
			if node['id'] == self.id:
				continue
			url = "http://" + node['ip'] + ":" + str(node['port']) + "/ring/receive"
			print(url)
			req = requests.post(url, json=ring_data)
			if (not req.status_code == 200):
				print("Problem")
				exit(1)


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
	def create_transaction(self, sender, receiver, signature, amount, inputs):
		# finder sender's id and balance and make sure it's sufficient
		sender_id = next(item for item in self.ring if item["ip"] == sender)['id'] # max n iterations
		sender_wallet_NBCs = self.get_wallet_balance(sender_id)
		if sender_wallet_NBCs < amount:
			print("Error: insufficent balance")
			return
		recipient_id = next(item for item in self.ring if item["ip"] == receiver)['id'] # max n iterations

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
		return transaction

		


	'''
	Broadcasts a transaction to other nodes
	'''
	def broadcast_transaction(self):
		for node in self.ring:
			requests.post("http://" + node['ip'] + ":" + node['port'] + "/transaction/receive")





	def validate_transaction(self, transaction):
		#use of signature and NBCs balance
		verified = transaction.verify_signature()
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
		else:
			print("Error")
			return



	def add_transaction_to_block(self, transaction):
		#if enough transactions mine
		self.chain.blocks[-1].add_transaction(transaction)
		if len(self.chain.blocks[-1].transcations) == self.chain.capacity:
			self.mine_block()



	def mine_block(self):
		timestamp = None
		nonce = randint(0, 2^32)
		while (True):
			sha_str = SHA256.new(nonce).hexdigest()
			if sha_str.startswith('0' * config.difficulty):
				timestamp = datetime.datetime.now().timestamp()
				break

			nonce = (nonce + 1) % (2^32)
		self.broadcast_block(nonce, timestamp)


	def broadcast_block(self, nonce, timestamp):
		for node in self.ring:
			requests.post("http://" + node['ip'] + ":" + node['port'] + "/block/add") # create endpoint in rest


		

	# def valid_proof(.., difficulty=MINING_DIFFICULTY):




	# #concensus functions

	# def valid_chain(self, chain):
	# 	#check for the longer chain accroose all nodes


	# def resolve_conflicts(self):
	# 	#resolve correct chain



