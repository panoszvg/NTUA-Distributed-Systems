import copy
import json
import time
from random import randint
import jsonpickle
from collections import deque
from block import Block
from blockchain import Blockchain
from transaction import Transaction
from transaction_io import Transaction_Input, Transaction_Output
from wallet import Wallet
import requests
import config
import _thread, threading

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
		validated blockchain that exists in this node
	current_block: Block
		block that is currently being modified, when it gets a nonce, becomes part of chain
	id: int
		number that represents a node (0, ..., n-1)
	current_id_count: int
		how many nodes exist - basically size of ring
	UTXOs: list of list of Transaction_Output
		list of UTXOs for each node
	block_received: bool
		boolean that signifies whether a block was received, useful for stopping the mining process
	mining: bool
		boolean that signifies whether this node is currently mining
	'''
	def __init__(self, ip, port, id):
		self.chain = Blockchain(config.capacity)
		self.current_block = Block(-1, -1)
		self.id = id
		self.current_id_count = id # will be updated in main
		self.UTXOs = []
		self.wallet = self.generate_wallet()
		self.ip = ip
		self.port = port
		self.ring = []
		self.block_received = False
		self.mining = False
		self.pending_transactions = deque()
		self.lock = threading.Lock()
		# threading.Thread(target=self.worker, daemon=True).start() # Turn-on the worker thread.
		

	def worker(self):
		while True:
			while len(self.pending_transactions) == 0:
				pass
			# if self.pending_transactions.empty():
			# 	return
			# flag = True
			while not self.lock.acquire(blocking=False):
				# flag = 
				print("Blocking in worker")
			print("Out of loop ----------------")
			print("After lock")
			try:
				transaction = self.pending_transactions.popleft()
			except:
				print("Failed mothafucka")
				if self.lock.locked():
					self.lock.release()
				continue

			print(f'Working on {transaction}')
			valid_transaction = self.validate_transaction(transaction)
			if valid_transaction:
				print("Valid transaction")
				self.add_transaction_to_block(transaction)
			print(f'Finished {transaction}')
			if self.lock.locked():
				self.lock.release()
			print("After release")
			print("Wallet: " + str(self.get_wallet_balance(self.id)) + " NBC")


	'''
	Get balance of a wallet in a node by adding its UTXOs
	that exist in current node (every node is always up to date)

	Parameters:
	-----------
	id: int
		the id of the node in order to search UTXOs (list of list of Transaction_Output)

	return: int
		the amount of NBC in a node
	'''
	def get_wallet_balance(self, id):
		sum = 0
		for utxo in self.UTXOs[id]:
			sum += utxo.amount
		return sum

	'''
	For debugging purposes
	'''
	def print_utxos(self):
		for i in range(0, len(self.ring)):
			print("Node #" + str(i))
			for utxo in self.UTXOs[i]:
				print(utxo.to_dict())
			print()

	'''
	Get transactions that exist in the last block

	return: list of Transaction
	'''
	def view_transactions(self):
		transactions_obj = self.current_block.transactions
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
				inputs.append(Transaction_Input(transaction.id))
				if sum >= amount:
					return (inputs, sum)
		else:
			return None

	'''
	Creates a new Block object and returns it

	Parameters:
	-----------
	previous_hash: str
		hash of the previous block, needed for validation of chain
	index: int
		index of current block

	return: Block
	'''
	def create_new_block(self, previous_hash, index):
		return Block(previous_hash, index)
		

	'''
	Creates a new wallet, including a new pair of private/public key using RSA.
	Implementation is in constructor of Wallet class in 'wallet.py'

	return: Wallet
	'''
	def generate_wallet(self):
		return Wallet()


	'''
	Add this node to the ring; only the bootstrap node can add a node to the ring after checking his wallet and ip:port address
	bootstrap node informs all other nodes and gives the request node an id and 100 NBCs

	return: None
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

	return: Node
	'''
	def initialize_nodes(self):
		time.sleep(1)
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
			inputs, inputs_sum = self.get_transaction_inputs(100) # no need to check if it returns None, it's always correct
			transaction = self.create_transaction(
				sender_ip=self.ring[self.id]['ip'],
				sender_port=self.ring[self.id]['port'],
				receiver_ip=node['ip'],
				receiver_port=node['port'],
				signature=self.wallet.private_key,
				amount=100,
				inputs=inputs,
				inputs_sum=inputs_sum
			)
			self.validate_transaction(transaction) # otherwise do manually
			self.broadcast_transaction(transaction)


	'''
	Creates a transaction with Transaction Inputs/Outputs. Don't assume it is correct - and 
	in case it isn't there is an extra check in validate_transaction() (for extra security)

	Parameters:
	-----------
	sender_ip: str
		IP of the node that sends NBC
	sender_port: int
		Port of the node that sends NBC
	receiver_ip: str
		IP of the node that receives NBC
	receiver_port: int
		Port of the node that receives NBC
	signature: str
		private key of the sender
	amount: int
		the amount of NBC to be sent
	inputs: list of Transaction_Input
		list that contains previous UTXO ids
	inputs_sum: int
		amount of NBCs that exist in inputs

	return: Transaction
	'''
	def create_transaction(self, sender_ip, sender_port, receiver_ip, receiver_port, signature, amount, inputs, inputs_sum):
		# finder sender's id and balance and make sure it's sufficient
		sender_id = next(item for item in self.ring if item["ip"] == sender_ip and item["port"] == sender_port)['id'] # max n iterations
		sender_wallet_NBCs = self.get_wallet_balance(sender_id)
		if sender_wallet_NBCs < amount:
			print("Error: insufficent balance")
			return
		recipient_id = next(item for item in self.ring if item["ip"] == receiver_ip and item["port"] == receiver_port)['id'] # max n iterations

		transaction = Transaction(self.ring[sender_id]['public_key'], self.ring[recipient_id]['public_key'], amount, inputs)
		transaction.sign_transaction(signature)
		output_sender = Transaction_Output(
							transaction_id=transaction.transaction_id,
							recipient=sender_id,
							amount=inputs_sum - amount
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

	Parameters:
	-----------
	transaction: Transaction
		transaction to be broadcasted

	return: None
	'''
	def broadcast_transaction(self, transaction):
		print("Broadcasting...")
		json = { 'transaction': jsonpickle.encode(transaction) }
		for node in self.ring:
			if node['id'] == self.id:
				continue
			requests.post("http://" + node['ip'] + ":" + str(node['port']) + "/transaction/receive", json=json)
		print("Finished broadcasting")


	'''
	Validates a transaction's signature, removes UTXOs that are given as inputs
	and adds UTXOs that are given as outputs

	Parameters:
	-----------
	transaction: Transaction
		transaction to be validated

	return: bool
		whether transaction is valid or not
	'''
	def validate_transaction(self, transaction):
		# use of signature and NBCs balance
		verified = transaction.verify_signature()
		############## also check for sufficient balance
		if verified:
			# find id of sender
			sender_id = next(item for item in self.ring if item["public_key"] == transaction.sender_address)['id'] # max n iterations
			# for that sender, find all UTXOs that correspond to the inputs and delete them
			for input in transaction.transaction_inputs:
				utxo_to_be_deleted = next((x for x in self.UTXOs[sender_id] if x.id == input.previous_output_id), None)
				try:
					self.UTXOs[sender_id].remove(utxo_to_be_deleted)
				except:
					# if self.lock.locked():
					# 	self.lock.release()
					_thread.start_new_thread(self.resolve_conflicts, ())
					return False
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

	return None
	'''
	def add_transaction_to_block(self, transaction):
		#if enough transactions mine
		self.current_block.add_transaction(transaction)
		if len(self.current_block.transactions) == self.chain.capacity:
			_thread.start_new_thread(self.mine_block, ())
		if self.lock.locked():
			self.lock.release()
		return

	'''
	Mines a block: searches for the right nonce, and when it
	finds it and broadcasts the block to the other nodes

	return: None
	'''
	def mine_block(self):
		print("Mining")
		self.mining = True
		nonce = randint(0, 2**64)
		block = self.current_block
		while (True):
			if self.block_received:
				self.block_received = False
				self.mining = False
				return # stop mining
			block.nonce = nonce
			block.current_hash = block.myHash()

			if block.current_hash.startswith('0' * config.difficulty):
				self.mining = False
				break

			nonce = (nonce + 1) % (2**64)

		block.index = len(self.chain.blocks)
		self.chain.blocks.append(block)
		self.current_block = Block(block.current_hash, block.index + 1)
		self.broadcast_block(block)


	'''
	Broadcasts a block to the other nodes

	Parameters:
	-----------
	block: Block
		the block with nonce and current_hash defined

	return: None
	'''
	def broadcast_block(self, block):
		for node in self.ring:
			if node['id'] == self.id:
				continue
			requests.post("http://" + node['ip'] + ":" + str(node['port']) + "/block/add", json={ 'block' : jsonpickle.encode(copy.deepcopy(block)) })


		
	'''
	Validate the current and previous hash of block received by another node

	Parameters:
	-----------
	block: Block
		the block received
	difficulty: int
		how many 0s the hash must have as a prefix

	return: bool
		whether block is valid or not
	'''
	def validate_block(self, block):
		if block.previous_hash == self.chain.blocks[-1].current_hash and block.current_hash.startswith('0'*config.difficulty):
			return True
		return False


	# #concensus functions

	'''
	Validate the blockchain received, basically call validate_block() for every block except genesis

	Parameters: 
	-----------
	chain: Blockchain
		blockchain received that needs to be validated

	return: bool
		whether blockchain received is valid or not
	'''
	def validate_chain(self, chain):
		for block in chain.blocks:
			if block.index != 0: # not genesis
				valid_block = self.validate_block(block)
				if not valid_block:
					return False
		return True


	def resolve_conflicts(self):
		#resolve correct chain
		max_len = 0
		max_info = None
		max_id = -1
		for node in self.ring:
			if node['id'] == self.id:
				continue
			url = url = "http://" + node['ip'] + ":" + str(node['port']) + "/chain/get"
			req = requests.get(url)
			if (not req.status_code == 200):
				print("Status code not 200")
				exit(1)
			if len(jsonpickle.decode(req.json()['chain']).blocks) > max_len:
				max_len = len(jsonpickle.decode(req.json()['chain']).blocks)
				max_info = req.json()

		while not self.lock.acquire(blocking=False):
			print("Blocking in resolving conflicts")
		self.chain = jsonpickle.decode(max_info['chain'])
		# self.UTXOs = jsonpickle.decode(max_info['UTXO'])
		# self.pending_transactions = jsonpickle.decode(max_info['pending_transactions'])
		# self.current_block = self.create_new_block(self.chain.blocks[-1].current_hash, max_len)
		self.current_block = jsonpickle.decode(max_info['current_block'])
		if self.lock.locked():
			self.lock.release()
		print("After resolving conflicts")
		print("Wallet: " + str(self.get_wallet_balance(self.id)))