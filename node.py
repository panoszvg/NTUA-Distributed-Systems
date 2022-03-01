from ipaddress import ip_address
from block import Block
from blockchain import Blockchain
from transaction import Transaction
from transaction_io import Transaction_Output
from wallet import Wallet
import requests

class Node:
	current_id_count = 0

	'''
	Initialize a node in the network

	Attributes
	----------
	NBC: int
		the amount of coins this node possesses
	wallet: Wallet
		the Wallet object of this node
	ring: list of dict
		here we store information for every node, as its id, its address (ip:port) its public key and its balance 
	chain: Blockchain
		blockchain that exists in this node
	id: int
		number that represents a node (0, ..., n-1)
	UTXOs: list of list of Transaction_Output
		list of UTXOs for each node
	'''
	def __init__(self, ip, port):
		self.NBC = 0 # change to 100*N for bootstrap
		self.chain = Blockchain()
		self.id = Node.current_id_count
		Node.current_id_count += 1
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
	def register_node_to_ring(self, id, ip, port, public_key, amount=0):
		self.ring.append(dict(
			id = id,
			ip = ip,
			port = port,
			public_key = public_key,
			amount = amount
		))
		self.UTXOs.append([])

	'''
	Method to initialize nodes other than bootstrap, it is called after the other Node objects have been
	created and added to ring variable. This method broadcasts ring to the other nodes and creates initial
	transactions to give other nodes their first 100 NBC.
	'''
	def initialize_nodes(self):
		for node in self.ring:
			requests.post("http://" + node['ip'] + ":" + node['port'])


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



	# def add_transaction_to_block():
	# 	#if enough transactions  mine



	# def mine_block():



	# def broadcast_block():


		

	# def valid_proof(.., difficulty=MINING_DIFFICULTY):




	# #concensus functions

	# def valid_chain(self, chain):
	# 	#check for the longer chain accroose all nodes


	# def resolve_conflicts(self):
	# 	#resolve correct chain



