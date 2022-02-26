from ipaddress import ip_address
import block
import wallet

class node:

	'''
	Initialize a node in the network

	Attributes
	----------
	NBC: int
		the amount of coins this node possesses
	wallet: Wallet
		the Wallet object of this node
	ring: list of dicts
		here we store information for every node, as its id, its address (ip:port) its public key and its balance 


	'''
	def __init__(self, ip, port):
		self.NBC=100;
		##set

		#self.chain
		#self.current_id_count
		#self.NBCs
		self.wallet = self.generate_wallet()
		self.ip = ip
		self.port = port
		self.ring = []




	# def create_new_block():
		

	'''
	Creates a new wallet, including a new pair of private/public key using RSA.
	Implementation is in constructor of Wallet class in 'wallet.py'
	'''
	def generate_wallet():
		return wallet.Wallet()


	def register_node_to_ring():
		#add this node to the ring, only the bootstrap node can add a node to the ring after checking his wallet and ip:port address
		#bottstrap node informs all other nodes and gives the request node an id and 100 NBCs


	def create_transaction(sender, receiver, signature):
		#remember to broadcast it


	def broadcast_transaction():





	def validate_transaction():
		#use of signature and NBCs balance


	def add_transaction_to_block():
		#if enough transactions  mine



	def mine_block():



	def broadcast_block():


		

	def valid_proof(.., difficulty=MINING_DIFFICULTY):




	#concensus functions

	def valid_chain(self, chain):
		#check for the longer chain accroose all nodes


	def resolve_conflicts(self):
		#resolve correct chain



