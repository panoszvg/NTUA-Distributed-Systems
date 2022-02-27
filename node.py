from ipaddress import ip_address
from block import Block
from blockchain import Blockchain
from transaction import Transaction
from wallet import Wallet

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

	'''
	def __init__(self, ip, port):
		self.NBC = 0 # change to 100*N for bootstrap
		self.chain = Blockchain()
		self.id = None
		#self.NBCs
		self.wallet = self.generate_wallet()
		self.ip = ip
		self.port = port
		self.ring = []



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
	def register_node_to_ring(self, ip, port, public_key, amount=0):
		self.ring.append(dict(
			ip = ip,
			port = port,
			public_key = public_key,
			amount = amount
		))
		# transaction = Transaction(self.ip, ip, 100, )

	'''
	Method to initialize nodes other than bootstrap, it is called after the other Node objects have been
	created and added to ring variable. This method broadcasts ring to the other nodes and creates initial
	transactions to give other nodes their first 100 NBC.
	'''
	# def initialize_nodes(self):
		# for node in self.ring:
		# 	#broadcast ring to node


	# def create_transaction(sender, receiver, signature):
	# 	#remember to broadcast it


	# def broadcast_transaction():





	# def validate_transaction():
	# 	#use of signature and NBCs balance


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



