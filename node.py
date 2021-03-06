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
import threading

class Node:

	'''
	Initialize a node in the network

	Attributes
	----------
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
	pending_UTXOs: list of list of Transaction_Output
		temporary changes made to UTXOs while making transactions:
			- in case a block is mined they are copied to UTXOs
			- in case a block is received they are discarded and are then brought up to date with the changes received
	wallet: Wallet
		the Wallet object of this node
	ip: str
		string that represents the ip of this node, used with port
	port: int
		number that represents the port that this node lists node, used with ip
	ring: list of dict
		here we store information for every node, as its id, its address (ip:port) its public key
	received_block: bool
		boolean that signifies whether a block was received, useful for stopping the mining process
	block_received: Block
		Block object that is set in endpoint when a block is received
	mining: bool
		boolean that signifies whether this node is currently mining
	pending_transactions: deque of Transaction
		deque that holds all transactions to be processed, both incoming and self-generated
	lock: Lock
		lock to use when accessing critical sections in code, 
		between transactions created in simulation/client, processed in worker and when resolving conflicts
	begin_working: bool
		boolean that is set after first transactions for 100 NBC are performed
	simulation_start_time: time
		time object to use for simulations
	resolving_conflicts: bool
		boolean to use when resolving conflicts
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
		self.received_block = False
		self.block_received = None
		self.mining = False
		self.pending_transactions = deque()
		self.lock = threading.Lock()
		self.begin_working = False
		self.simulation_start_time = None
		self.resolving_conflicts = False
		

	'''
	This is the function that processes transactions in pending_transactions deque, validates them,
	if it's made by current node broadcasts them and then adds them to current_block.
	'''
	def worker(self):
		while True:
			# wait until conflicts are resolved
			while self.resolving_conflicts:
				pass
			# while there are no pending transactions, only perform
			# changes if a correct block is received
			while len(self.pending_transactions) == 0:
				if self.received_block:
					if DEBUG:
						print("Have received a block while working - trying to lock")
					while not self.lock.acquire(blocking=False):
						pass
					if DEBUG:
						print("Acquired lock in worker")
					if self.block_received == None and self.lock.locked():
						self.lock.release()
						continue
					if self.validate_block(self.block_received):
						self.process_block_received()
					self.received_block = False
					self.mining = False
					self.block_received = None
					if self.lock.locked():
						self.lock.release()
					continue
				pass
			while not self.lock.acquire(blocking=False):
				pass
			if DEBUG:
				print("Acquired lock in worker")
			if self.received_block:
				if DEBUG:
					print("Have received a block while working - already locked")
				if self.validate_block(self.block_received):
					self.process_block_received()
				self.received_block = False
				self.mining = False
				self.block_received = None
				if self.lock.locked():
					self.lock.release()
				continue
			try:
				transaction = self.pending_transactions.popleft()
			except:
				if self.lock.locked():
					self.lock.release()
				continue

			# if transaction is created by current node 'recreate' it
			if transaction.sender_address == self.wallet.public_key:
				transaction = self.recreate_node_transaction(transaction)
			
			# if transaction already exists in chain, it's duplicate, do nothing
			if transaction == None or self.transaction_exists(transaction):
				if self.lock.locked():
					self.lock.release()
				continue

			if DEBUG:
				print("Trying to validate txn in worker")
			while self.mining:
				pass
			valid_transaction = self.validate_transaction(transaction)
			if valid_transaction:
				# if transaction is correct and by current node, also broadcast
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

	'''
	Get the 'index' of a transaction, useful so as to not mess with first transactions
	that transfer the initial amount of NBCs to all nodes

	Parameters:
	-----------
	transaction_id: string (hex)
		string that represents the id (hexstring) of a transaction

	return: int
		returns 'index' of transaction
	'''
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

	'''
	Get info on whether a transaction exists in chain or in current_block

	Parameters:
	-----------
	transaction: Transaction
		the transaction to be searched

	return: bool
		true if it exists, false if it doesn't
	'''
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

	return: None
	'''
	def initialize_nodes(self):
		# copy UTXOs to pending_UTXOs
		for utxo in self.UTXOs:
			self.pending_UTXOs.append(copy.deepcopy(utxo))
		time.sleep(15) # because it takes forever for other nodes to start their Flask servers in okeanos VMs

		data = { 
			'ring': jsonpickle.encode(self.ring),
			'current_block': jsonpickle.encode(self.current_block),
			'chain': jsonpickle.encode(self.chain),
			'UTXOs': jsonpickle.encode(self.UTXOs)
			}

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

			while self.mining:
				pass

			inputs, inputs_sum = self.get_transaction_inputs(100) # no need to check if it returns None, it's always correct
			transaction = self.create_transaction(
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
		
		for node in self.ring:
			if node['id'] == self.id:
				continue
			url = "http://" + node['ip'] + ":" + str(node['port']) + "/begin"
			req = requests.post(url)
			if (not req.status_code == 200):
				print("Problem")
				exit(1)

		self.begin_working = True


	'''
	Creates a transaction with Transaction Inputs/Outputs. Don't assume it is correct - and 
	in case it isn't there is an extra check in validate_transaction() (for extra security)

	Parameters:
	-----------
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
	def create_transaction(self, receiver_ip, receiver_port, amount, inputs, inputs_sum):
		# finder sender's id and balance and make sure it's sufficient
		sender_id = self.id
		sender_wallet_NBCs = self.get_wallet_balance(sender_id, True)
		if sender_wallet_NBCs < amount:
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
		verified = transaction.verify_signature()
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
							for i in range(0,config.nodes):
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

		while self.mining:
			pass

		self.current_block.add_transaction(transaction)
		if DEBUG:
			print("Adding txn to block, block now contains " + str(len(self.current_block.transactions)) + " transactions")
		
		#if enough transactions mine
		if len(self.current_block.transactions) == self.chain.capacity:
			self.mine_block()
		if self.lock.locked():
			self.lock.release()
		return


	'''
	Function that is called when a block is received and is correct.
	Adds block to current chain and makes changes to UTXOs according to transactions in correct block. 
	Discards current_block that has been created and re-initializes it, discards pending_UTXOs and brings 
	them up-to-date with correct UTXOs changes made using the correct block.

	Parameters: none, but using self.block_received since it is set in endpoint /block/add
	'''
	def process_block_received(self):
		while self.block_received == None:
			pass

		self.reinsert_transactions([self.current_block], self.block_received)
		self.add_UTXOS(self.block_received)

		# remove transactions from pending_transactions that exist in new block received
		for txn in self.block_received.transactions:
			for pending_txn in self.pending_transactions.copy():
				if txn.transaction_id == pending_txn.transaction_id and txn.sender_address == self.wallet.public_key:
					self.pending_transactions.remove(pending_txn)

		# handle blocks
		self.chain.blocks.append(self.block_received)
		self.current_block = Block(self.block_received.current_hash, self.block_received.index + 1)

		# change pending UTXOs to new UTXOs
		self.pending_UTXOs = []
		for utxo in self.UTXOs:
			self.pending_UTXOs.append(copy.deepcopy(utxo))

		if DEBUG:
			print("NEW UTXOS")
			for i in range(0,config.nodes):
				for utxo in self.pending_UTXOs[i]:
					print(utxo.to_dict())
			print()

		if config.simulation:
			if self.simulation_start_time != None:
				print("Block received at: " + str(time.time() - self.simulation_start_time) +" sec.")
			else:
				print("Block received at: " + str(time.time()))
			# print("New Balances:")
			# for i in range(0, config.nodes):
			# 	print("Wallet: " + str(self.get_wallet_balance(i)) + " NBC")
			# print("Current chain (last 5):")
			# for block in self.chain.blocks[-5:]:
			# 	print(str(block.index) + ": " + str(block.current_hash))
			# print()

	'''
	Mines a block: searches for the right nonce, and when it
	finds it and broadcasts the block to the other nodes. If a block is 
	received while mining, calls process_block_received() and returns.

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
			if self.resolving_conflicts:
				return
			if self.received_block:
				self.process_block_received()
				self.received_block = False
				self.mining = False
				self.block_received = None
				if self.lock.locked():
					self.lock.release()
				return # stop mining
			block.nonce = nonce
			block.current_hash = block.myHash()

			if block.current_hash.startswith('0' * config.difficulty):
				break

			nonce = (nonce + 1) % (2**64)

		if DEBUG:
			print("FOUND SOLUTION with hash: " + str(block.current_hash))
			for transaction in block.transactions:
				sender_id = None
				receiver_id = None
				for item in self.ring:
					if item["public_key"] == transaction.sender_address:
						sender_id = item["id"]
					if item["public_key"] == transaction.receiver_address:
						receiver_id = item["id"]
				print("Sender: " + str(sender_id) + ", Receiver: " + str(receiver_id) + ", amount: " + str(transaction.amount))
				for t_input in transaction.transaction_inputs:
					print("\tInput: { Owner" + str(t_input.owner) + ", Amount: " + str(t_input.amount) + " }")
				for t_output in transaction.transaction_outputs:
					print("\tOutput: { Recipient: " + str(t_output.recipient) + ", Amount: " + str(t_output.amount) + " }")
			print()
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
			for i in range(0,config.nodes):
				for utxo in self.pending_UTXOs[i]:
					print(utxo.to_dict())
			print()

		if config.simulation:
			if self.simulation_start_time != None:
				print("Block mined at: " + str(time.time() - self.simulation_start_time) +" sec.")
			else:
				print("Block mined at: " + str(time.time()))
			# print("New Balances:")
			# for i in range(0, config.nodes):
			# 	print("Wallet: " + str(self.get_wallet_balance(i)) + " NBC")
			# print("Current chain (last 5):")
			# for block in self.chain.blocks[-5:]:
			# 	print(str(block.index) + ": " + str(block.current_hash))
			# print()

		self.mining = False
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
			requests.post("http://" + node['ip'] + ":" + str(node['port']) + "/block/add", json={ 'block' : jsonpickle.encode(copy.deepcopy(block)), 'UTXOs': jsonpickle.encode(copy.deepcopy(self.UTXOs)) })


		
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


	'''
	Function called when making changes to UTXOs using transactions of received block (assumed to be correct).
	Basically performs the same job as validate_transaction, but without returning in case of failure.

	Parameters:
	-----------
	block: Block
		correct block received from other node.
	'''
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


	'''
	Function that is called when transactions have been added to current_block, but aren't correct
	because node doesn't mine block before someone else. Since transactions are discarded by every node,
	every node is responsible for recreating their own transactions. Could have re-added them to pending_transactions,
	but since transactions require specific Transaction_Input/Transaction_Output objects, they must be recreated.

	Parameters:
	-----------
	blocks: list of Block
		blocks to search for failed transactions made by self and add them back to pending_transactions
	block_received: Block
		correct block to check whether failed self transactions already exist in, and  
		not recreate them (therefore correct transactions but mined by other node)
	'''
	def reinsert_transactions(self, blocks, block_received=None):
		txns_to_recreate = []
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
					for incoming_txn in block_received.transactions:
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
						# self.pending_transactions.append(transaction)
						txns_to_recreate.append(transaction)

		# add transactions to recreate before other self transactions in case they exists, so that
		# they are processed in order all over again
		first_node_txn = next((x for x in self.pending_transactions if x.sender_address == self.wallet.public_key), None)
		if first_node_txn != None:
			idx = self.pending_transactions.index(first_node_txn)
			for txn_to_recreate in reversed(txns_to_recreate):
				self.pending_transactions.insert(idx, txn_to_recreate)
		else:
			for txn_to_recreate in reversed(txns_to_recreate):
				self.pending_transactions.append(txn_to_recreate)


	'''
	Function that re-creates node transaction, essentially needed for re-findind inputs in case it's 
	a failed transaction that needs to be re-processed (since it requires specific Transaction_Input/Transaction_Output objects).

	Parameters:
	-----------
	transaction: Transaction
		transaction made by self to re-create

	return: Transaction | None
		if re-creation of transaction is successful, return Transaction object, otherwise None
	'''
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
			return

		inputs, inputs_sum = temp

		id = next((x['id'] for x in self.ring if x['public_key'] == transaction.receiver_address), None)

		# create transaction
		new_transaction = self.create_transaction(
            receiver_ip=str(self.ring[id]['ip']),
            receiver_port=self.ring[id]['port'],
            amount=transaction.amount,
            inputs=inputs,
            inputs_sum=inputs_sum
        )
		if transaction != None:
			new_transaction.transaction_id = transaction.transaction_id
		return new_transaction


	'''
	Function to undo 'correct' UTXOs that have been added to chain but ultimately are in wrong branch of chain.
	Basiscally, undo all transactions (going backwards) by re-creating all the UTXOs that are inputs and remove
	all the UTXOs that are outputs (since when adding them the reverse happens; inputs are removed and outputs are added).

	Parameters:
	-----------
	blocks: list of Block
		blocks in chain to be undone
	'''
	def undo_UTXOs(self, blocks):
		# add previous UTXO(s)
		for block in reversed(blocks):
			for transaction in reversed(block.transactions):
				for txn_input in transaction.transaction_inputs:
					self.UTXOs[txn_input.owner].append(Transaction_Output(transaction.transaction_id, txn_input.owner, txn_input.amount))
		
		# remove current UTXOs
		for block in reversed(blocks):
			for transaction in reversed(block.transactions):
				for txn_output in transaction.transaction_outputs:
					for x in self.UTXOs[txn_output.recipient]:
						if x.id == txn_output.id:
							self.UTXOs[txn_output.recipient].remove(x)


	'''
	Function that resolves conflicts if a block is received that is not valid. It asks other nodes for
	their chain and if they have a chain longer than its own, it brings this node up-to-date with correct branch
	by removing the blocks that are in the wrong branch (and undoing respective transactions) and adding the 
	correct blocks (and by performing the necessary transactions that exist in block).
	'''
	def resolve_conflicts(self):
		if DEBUG:
			print("In Resolving Conflicts with chain:")
			for block in self.chain.blocks:
				print(str(block.index) + ": " + str(block.current_hash))
			print("And UTXOs:")
			for i in range(0,config.nodes):
				for utxo in self.pending_UTXOs[i]:
					print(utxo.to_dict())
			print()

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

		if max_len <= len(self.chain.blocks):
			if DEBUG:
				print("Exiting cause I'm right: " + str(max_len) + " <= " + str(len(self.chain.blocks)))
			self.resolving_conflicts = False
			return

		while not self.lock.acquire(blocking=False):
			pass

		self.current_block = jsonpickle.decode(max_info['current_block'])
		incoming_chain = jsonpickle.decode(max_info['chain'])
		
		# decide how many current blocks to revert
		blocks_to_add = 0
		old_block_index = None

		if DEBUG:
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
					old_block_index = self.chain.blocks.index(block)
					if DEBUG:
						print("Found adding blocks to be " + str(blocks_to_add) + " - breaking")
						print("Found index to be " + str(old_block_index) + "       - breaking")
					flag = True
					break
			if flag:
				break
			blocks_to_add += 1

		if blocks_to_add == 0:
			if DEBUG:
				print("Exiting cause I got no changes to do")
			self.block_received = None
			self.received_block = False
			if self.lock.locked():
				self.lock.release()
			self.resolving_conflicts = True
			return

		# undo UTXOs that exist in the wrong part of current chain
		self.undo_UTXOS(self.chain.blocks[old_block_index+1:])

		# perform transactions that exist in the right part of incoming chain
		for incoming_block in incoming_chain.blocks[-blocks_to_add:]:
			self.add_UTXOS(incoming_block)

		# create temporary block that holds all incoming correct transactions
		temp_block = copy.deepcopy(incoming_chain.blocks[-blocks_to_add])
		for incoming_block in incoming_chain.blocks[-blocks_to_add+1:]:
			for incoming_txn in incoming_block.transactions:
				temp_block.transactions.append(incoming_txn)

		# re-add transactions from non-valid part of chain (that also don't exist in incoming
		# chain and therefore haven't been processed yet) to pending_transactions
		for nonvalid_block in self.chain.blocks[old_block_index+1:]:
			for nonvalid_txn in nonvalid_block.transactions:
				if nonvalid_txn.transaction_id not in temp_block.transactions:
					self.pending_transactions.appendleft(nonvalid_txn)

		if DEBUG:
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

		if DEBUG:
			print("\nCurrent chain")
			for block in self.chain.blocks:
				print(str(block.index) + ": " + str(block.current_hash))

		if self.lock.locked():
			self.lock.release()
		self.resolving_conflicts = True
