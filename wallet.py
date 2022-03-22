from Crypto.PublicKey import RSA

class Wallet:

	'''
	Initialize a Wallet object that belongs to a Node in the network
	'''
	def __init__(self):
		rand_gen = RSA.generate(2048)
		self.public_key = rand_gen.publickey().exportKey().decode() 
		self.private_key = rand_gen.exportKey().decode() 
		#self_address
		self.transactions = []

	# def balance():

