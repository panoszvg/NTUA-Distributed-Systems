import copy
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
from config import DEBUG
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
		self.pending_UTXOs = []
		self.wallet = self.generate_wallet()
		self.ip = ip
		self.port = port
		self.ring = []
		self.block_received = False
		self.received_block = None
		self.old_valid_txns = 0
		self.mining = False
		self.pending_transactions = deque()
		self.lock = threading.Lock()
		

	def worker(self):
		while True:
			while len(self.pending_transactions) == 0:
				if self.block_received:
					if DEBUG:
						print("Have received a block while working - trying to lock")
					while not self.lock.acquire(blocking=False):
						pass
					if DEBUG:
						print("Acquired lock in worker")
					self.process_received_block()
					self.block_received = False
					self.mining = False
					self.received_block = None
					if self.lock.locked():
						self.lock.release()
					continue
				pass
			while not self.lock.acquire(blocking=False):
				pass
			if DEBUG:
				print("Acquired lock in worker")
			if self.block_received:
				if DEBUG:
					print("Have received a block while working - already locked")
				self.process_received_block()
				self.block_received = False
				self.mining = False
				self.received_block = None
				if self.lock.locked():
					self.lock.release()
				continue
			try:
				transaction = self.pending_transactions.popleft()
			except:
				if DEBUG:
					pass
					# print("Failed")
				if self.lock.locked():
					self.lock.release()
				continue

			if transaction.sender_address == self.wallet.public_key:
				transaction = self.recreate_node_transaction(transaction)
				self.old_valid_txns -= 1
			
			if transaction == None or self.transaction_exists(transaction):
				if self.lock.locked():
					self.lock.release()
				continue

			if DEBUG:
				print("Trying to validate txn in worker")
			valid_transaction = self.validate_transaction(transaction)
			if valid_transaction:
				if transaction.sender_address == self.wallet.public_key:
					self.broadcast_transaction(transaction)
				if DEBUG:
					print("Now processing pending transaction...")
				self.add_transaction_to_block(transaction)
			else:
				if DEBUG:
					print("Not valid txn")
			if self.lock.locked():
				self.lock.release()


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
	def get_wallet_balance(self, id, pending=True):
		sum = 0
		if pending:
			for utxo in self.pending_UTXOs[id]:
				sum += utxo.amount
		else:
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

	def get_transactions_number(self, transaction_id):
		counter = 0
		flag = False
		for block in self.chain.blocks:
			for transaction in block.transactions:
				if transaction.transaction_id == transaction_id:
					flag = True
					break
				else:
					counter += 1
			if flag:
				return counter
		for transaction in self.current_block.transactions:
			if transaction.transaction_id == transaction_id:
				flag = True
				break
			else:
				counter += 1
		return counter

	def transaction_exists(self, transaction):
		for block in reversed(self.chain.blocks):
			for txn in reversed(block.transactions):
				if txn.transaction_id == transaction.transaction_id:
					if DEBUG:
						print("It already exists, returning")
					return True
		for txn in reversed(self.current_block.transactions):
			if txn.transaction_id == transaction.transaction_id:
				if DEBUG:
					print("It already exists, returning")
				return True
		return False

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
		balance = self.get_wallet_balance(self.id, True)
		if balance >= amount:
			sum = 0
			inputs = [] # list of Transaction_Input to be used
			for transaction in self.pending_UTXOs[self.id]:
				sum += transaction.amount
				inputs.append(Transaction_Input(transaction.id, transaction.recipient, transaction.amount))
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
		# copy UTXOs to pending_UTXOs
		for utxo in self.UTXOs:
			self.pending_UTXOs.append(copy.deepcopy(utxo))
		time.sleep(1)

		data = { 
			'ring': jsonpickle.encode(self.ring),
			'current_block': jsonpickle.encode(self.current_block),
			'chain': jsonpickle.encode(self.chain),
			'UTXOs': jsonpickle.encode(self.UTXOs) }

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
				amount=100,
				inputs=inputs,
				inputs_sum=inputs_sum
			)
			valid_transaction = self.validate_transaction(transaction) # otherwise do manually
			self.broadcast_transaction(transaction)
			if valid_transaction:
				self.add_transaction_to_block(transaction)
			else:
				print("WTF") # leave it, because if it comes here there's something seriously wrong :)


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
	def create_transaction(self, sender_ip, sender_port, receiver_ip, receiver_port, amount, inputs, inputs_sum):
		# finder sender's id and balance and make sure it's sufficient
		sender_id = self.id
		sender_wallet_NBCs = self.get_wallet_balance(sender_id, True)
		if sender_wallet_NBCs < amount:
			print("Error: insufficent balance")
			return
		recipient_id = next(item for item in self.ring if item["ip"] == receiver_ip and item["port"] == receiver_port)['id'] # max n iterations

		transaction = Transaction(self.ring[sender_id]['public_key'], self.ring[recipient_id]['public_key'], amount, inputs)
		transaction.sign_transaction(self.wallet.private_key)
		output_sender = Transaction_Output(
							transaction_id=transaction.transaction_id,
							recipient=sender_id,
							amount=inputs_sum - amount
						)
		transaction.transaction_outputs.append(output_sender)

		if DEBUG:
			print("Created output for sender: " + str(output_sender.to_dict()))

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

	return: bool
		whether transaction is valid or not
	'''
	def validate_transaction(self, transaction):
		# use of signature and NBCs balance
		verified = transaction.verify_signature()
		############## also check for sufficient balance
		if verified:
			# find id of sender
			temp = None
			for item in self.ring:
				if item["public_key"] == transaction.sender_address:
					temp = item["id"]
			sender_id = temp
			# for that sender, find all UTXOs that correspond to the inputs and delete them
			for input in transaction.transaction_inputs:
				utxo_to_be_deleted = next((x for x in self.pending_UTXOs[sender_id] if x.id == input.previous_output_id), None)
				try:
					if utxo_to_be_deleted == None:
						if DEBUG:
							print("IT IS NONE")
							for i in range(0,5):
								for utxo in self.pending_UTXOs[i]:
									print(utxo.to_dict())
							print(str(input.previous_output_id) + " -> '" + str(sender_id) + "' $" + str(input.amount))
							print("\n")
					self.pending_UTXOs[sender_id].remove(utxo_to_be_deleted)
				except:
					return False
			# add all (both) outputs to UTXOs
			for output in transaction.transaction_outputs:
				node_id = output.recipient
				self.pending_UTXOs[node_id].append(output)
			return True
		else:
			print("Error - Wrong signature")
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
		if DEBUG:
			print("In adding txn to block, with block having txns: " + str(len(self.current_block.transactions)))
			sender_id = None
			receiver_id = None
			for item in self.ring:
				if item["public_key"] == transaction.sender_address:
					sender_id = item["id"]
				if item["public_key"] == transaction.receiver_address:
					receiver_id = item["id"]
			print("TXN => Sender: " + str(sender_id) + ", Receiver: " + str(receiver_id) + ", amount: " + str(transaction.amount))

		#if enough transactions mine
		while self.mining:
			pass
		self.current_block.add_transaction(transaction)
		if DEBUG:
			print("Adding txn to block, block now contains " + str(len(self.current_block.transactions)) + " transactions")
		if len(self.current_block.transactions) == self.chain.capacity:
			self.mine_block()
		if self.lock.locked():
			self.lock.release()
		return


	def process_received_block(self):
		while self.received_block == None:
			pass

		# add new UTXOs
		if self.received_block.index == len(self.chain.blocks):
			self.revert_UTXOS([self.current_block], self.received_block)
		self.add_UTXOS(self.received_block)
		# handle blocks
		self.chain.blocks.append(self.received_block)
		self.current_block = Block(self.received_block.current_hash, self.received_block.index + 1)

		# change pending UTXOs to new UTXOs
		self.pending_UTXOs = []
		for utxo in self.UTXOs:
			self.pending_UTXOs.append(copy.deepcopy(utxo))

		if DEBUG:
			print("NEW UTXOS")
			for i in range(0,5):
				for utxo in self.pending_UTXOs[i]:
					print(utxo.to_dict())
			print("\n")

	'''
	Mines a block: searches for the right nonce, and when it
	finds it and broadcasts the block to the other nodes

	return: None
	'''
	def mine_block(self):
		if DEBUG:
			print("In mining")
		self.mining = True
		nonce = randint(0, 2**64)
		block = self.current_block
		if block.previous_hash == -1 or 1:
			block.previous_hash = self.chain.blocks[-1].current_hash
		block.index = len(self.chain.blocks)
		while (True):
			if self.block_received:
				self.process_received_block()
				self.block_received = False
				self.mining = False
				self.received_block = None
				if self.lock.locked():
					self.lock.release()
				return # stop mining
			block.nonce = nonce
			block.current_hash = block.myHash()

			if block.current_hash.startswith('0' * config.difficulty):
				self.mining = False
				break

			nonce = (nonce + 1) % (2**64)

		if DEBUG:
			print("FOUND SOLUTION with hash: " + str(block.current_hash))
		self.chain.blocks.append(block)
		self.current_block = Block(block.current_hash, block.index + 1)
		# change UTXOs
		self.UTXOs = []
		for utxo in self.pending_UTXOs:
			self.UTXOs.append(copy.deepcopy(utxo))

		# remove all pending transactions of other nodes, since they
		# will be recreated - keep current node's since they're recreations
		for txn in self.pending_transactions.copy():
			if txn.sender_address != self.wallet.public_key:
				self.pending_transactions.remove(txn)

		if DEBUG:
			print("NEW UTXOS")
			for i in range(0,5):
				for utxo in self.pending_UTXOs[i]:
					print(utxo.to_dict())
			print("\n")

		if self.lock.locked():
			self.lock.release()
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
	def validate_block(self, block, previous_block=None):
		if previous_block == None:
			previous_block = self.chain.blocks[-1]
		if DEBUG:
			print("Previous block's hash: " + str(previous_block.current_hash))
			print("Current block's phash: " + str(block.previous_hash))
		if block.previous_hash == previous_block.current_hash and block.current_hash.startswith('0'*config.difficulty):
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
		for i in range(0, len(chain.blocks)):
			if i != 0: # not genesis
				valid_block = self.validate_block(chain.blocks[i], chain.blocks[i-1])
				if not valid_block:
					return False
		return True


	def add_UTXOS(self, block):
		for transaction in block.transactions:
			# find id of sender
			temp = None
			for item in self.ring:
				if item["public_key"] == transaction.sender_address:
					temp = item["id"]
			sender_id = temp
			# for that sender, find all UTXOs that correspond to the inputs and delete them
			for input in transaction.transaction_inputs:
				utxo_to_be_deleted = next((x for x in self.UTXOs[sender_id] if x.id == input.previous_output_id), None)
				for x in self.UTXOs[sender_id]:
					if x.id == input.previous_output_id:
						utxo_to_be_deleted = x
						break
				try:
					self.UTXOs[sender_id].remove(utxo_to_be_deleted)
				except:
					# if config.scalable:
					# 	_thread.start_new_thread(self.resolve_conflicts_scalable, ())
					# else:
					# 	_thread.start_new_thread(self.resolve_conflicts, ())
					pass
			# add all (both) outputs to UTXOs (if they don't already exist)
			for output in transaction.transaction_outputs:
				flag = True
				node_id = output.recipient
				for utxo in self.UTXOs[node_id]:
					if utxo.id == output.id:
						flag = False
						break
				if flag:
					self.UTXOs[node_id].append(output)
				else:
					pass
					if DEBUG:
						print("UTXO already exists, not adding it again")


	def revert_UTXOS(self, blocks, received_block=None):
		for block in blocks:
			for transaction in block.transactions:
				flag = False
				if DEBUG:
					print("Might want to redo txn with $$" + str(transaction.amount) + "  and tns #" + str(self.get_transactions_number(transaction_id=transaction.transaction_id)))
				if self.get_transactions_number(transaction_id=transaction.transaction_id) < config.nodes:
					continue
				if DEBUG:
					print("Checking txn: " + str(transaction.to_dict()['transaction_id']) + " $" + str(transaction.to_dict()['amount']))
				if transaction.sender_address == self.wallet.public_key:
					for incoming_txn in received_block.transactions:
						if DEBUG:
							print("   with txn: " + str(incoming_txn.to_dict()['transaction_id']) + " $" + str(incoming_txn.to_dict()['amount']))
						if incoming_txn.transaction_id == transaction.transaction_id:
							flag = True
							break
					if flag:
						if DEBUG:
							print("Not recreating txn with amount: "+ str(transaction.amount) +", since it exists in incoming block :)")
						continue
					else:
						if DEBUG:
							print("Recreating transaction " + str(transaction.to_dict()['amount']))
						self.old_valid_txns += 1
						self.pending_transactions.append(transaction)


	def recreate_node_transaction(self, transaction):
		if DEBUG:
			print("In RECREATE with amount: " + str(transaction.amount) + " and id: " + str(transaction.transaction_id))
		if self.transaction_exists(transaction):
			return 
		temp = self.get_transaction_inputs(transaction.amount)
		if temp == None:
			if DEBUG:
				print("Wallet doesn't have sufficient funds to make this transaction")
				print("Wallet: " + str(self.get_wallet_balance(self.id, True)) + " NBC")
				print()
				if self.lock.locked():
					self.lock.release()
			return

		inputs, inputs_sum = temp

		id = next((x['id'] for x in self.ring if x['public_key'] == transaction.receiver_address), None)

		# create transaction
		new_transaction = self.create_transaction(
            sender_ip=self.ip,
            sender_port=self.port,
            receiver_ip=str(self.ring[id]['ip']),
            receiver_port=self.ring[id]['port'],
            amount=transaction.amount,
            inputs=inputs,
            inputs_sum=inputs_sum
        )
		new_transaction.transaction_id = transaction.transaction_id
		return new_transaction


	def resolve_conflicts(self):
		print("In Resolving Conflicts")
		#resolve correct chain
		max_len = 0
		max_info = None
		for node in self.ring:
			if node['id'] == self.id:
				continue
			url = "http://" + node['ip'] + ":" + str(node['port']) + "/chain/get"
			req = requests.get(url)
			if (not req.status_code == 200):
				print("Status code not 200")
				exit(1)
			if len(jsonpickle.decode(req.json()['chain']).blocks) > max_len:
				max_len = len(jsonpickle.decode(req.json()['chain']).blocks)
				max_info = req.json()


		while not self.lock.acquire(blocking=False):
			pass
		# self.chain = jsonpickle.decode(max_info['chain'])
		# self.current_block = jsonpickle.decode(max_info['current_block'])
		incoming_chain = jsonpickle.decode(max_info['chain'])
		if self.validate_chain(incoming_chain):
			pass
		else:
			print("CHAIN RECEIVED IS NOT VALID")
			if self.lock.locked():
				self.lock.release()
			return
		
		# decide how many current blocks to revert
		blocks_to_add = 0
		old_block_index = None

		print("\nCurrent chain:")
		for block in self.chain.blocks:
			print(str(block.index) + ": " + str(block.current_hash))
		print("\nIncoming chain:")
		for incoming_block in incoming_chain.blocks:
			print(str(incoming_block.index) + ": " + str(incoming_block.current_hash))
		print("\n")

		flag = False
		for incoming_block in reversed(incoming_chain.blocks):
			for block in reversed(self.chain.blocks):
				if incoming_block.current_hash == block.current_hash:
					print("Found adding blocks to be " + str(blocks_to_add) + " - breaking")
					old_block_index = self.chain.blocks.index(block)
					print("Found index to be " + str(old_block_index) + "       - breaking")
					flag = True
					break
			if flag:
				break
			blocks_to_add += 1

		if max_len <= len(self.chain.blocks):
			print("Exiting cause I'm right")
			if self.lock.locked():
				self.lock.release()
			return

		if blocks_to_add == 0:
			print("Exiting cause I got no changes to do")
			if self.lock.locked():
				self.lock.release()
			return

		self.revert_UTXOS(self.chain.blocks[old_block_index+1:])

		for incoming_block in incoming_chain.blocks[-blocks_to_add:]:
			self.add_UTXOS(incoming_block)

		print("\nCurrent chain to keep:")
		for block in self.chain.blocks[:old_block_index+1]:
			print(str(block.index) + ": " + str(block.current_hash))
		
		print("\nIncoming chain to add:")
		for incoming_block in incoming_chain.blocks[-blocks_to_add:]:
			print(str(incoming_block.index) + ": " + str(incoming_block.current_hash))
		print("\n")

		self.chain.blocks = self.chain.blocks[:old_block_index+1]
		for incoming_block in incoming_chain.blocks[-blocks_to_add:]:
			self.chain.blocks.append(incoming_block)

		# bring pending UTXOs up to date
		self.pending_UTXOs = []
		for utxo in self.UTXOs:
			self.pending_UTXOs.append(copy.deepcopy(utxo))

		if self.lock.locked():
			self.lock.release()


	'''
	This function resolves conflicts for scalable systems, since it first finds the node
	with max chain length, finds out which blocks it needs from it and requests that number
	of blocks from that node, to replace its own.
	'''
	def resolve_conflicts_scalable(self):
		#resolve correct chain
		max_len = 0
		max_info = None
		max_id = -1
		# find node with max chain length
		for node in self.ring:
			if node['id'] == self.id:
				continue
			url = "http://" + node['ip'] + ":" + str(node['port']) + "/chain/length"
			req = requests.get(url)
			if (not req.status_code == 200):
				print("Status code not 200")
				exit(1)
			if jsonpickle.decode(req.json()['length']) > max_len:
				max_id = node['id']
				max_len = jsonpickle.decode(req.json()['length'])
				max_info = jsonpickle.decode(req.json()['chain'])

		# find how many blocks to request
		request_length = 1
		for block in reversed(self.chain.blocks):
			pass
			if block.current_hash in max_info:
				break
			else:
				request_length += 1

		# request the last @request_length blocks from node with max chain length
		url = "http://" + self.ring[max_id]['ip'] + ":" + str(self.ring[max_id]['port']) + "/chain/get/" + str(request_length)
		req = requests.get(url)
		if (not req.status_code == 200):
			print("Status code not 200")
			exit(1)
		new_blocks = jsonpickle.decode(req.json()['blocks'])

		# replace last @request_length blocks of chain with blocks from node with max chain length
		while not self.lock.acquire(blocking=False):
			pass
		for i in range(0, request_length):
			self.chain.blocks.pop()
		for new_block in new_blocks:
			self.chain.blocks.append(new_block)
		self.current_block = jsonpickle.decode(req.json()['current_block'])

		if self.lock.locked():
			self.lock.release()