
import json
from Crypto.Hash import SHA512
import jsonpickle

class Block:
	'''
	Initialize a Block object with base information
	'''
	def __init__(self, previous_hash, index):
		self.index = index
		self.transactions = []
		self.nonce = 0
		self.current_hash = None # will change after it's hashed
		self.previous_hash = previous_hash
	
	'''
	Calculate current hash:
	Create a dict with block's information and encrypt it
	'''
	def myHash(self):
		block_info = json.dumps(dict(
			index = self.index,
			transactions = [item.to_dict() for item in self.transactions],
			nonce = self.nonce,
			previous_hash = self.previous_hash
		))
		return SHA512.new(block_info.encode()).hexdigest()

	'''
	Add a transaction to the block:
	Essentially append it to transactions list
	'''
	def add_transaction(self, transaction):
		self.transactions.append(transaction)
