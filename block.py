
import json
import datetime
from Crypto.Hash import SHA256
from pyparsing import traceParseAction
from transaction import Transaction



class Block:
	'''
	Initialize a Block object with base information
	'''
	def __init__(self, previous_hash, index):
		self.index = index
		self.timestamp = datetime.datetime.now().timestamp()
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
			timestamp = self.timestamp,
			transactions = self.transactions, # might need to unpack this
			nonce = self.nonce,
			previous_hash = self.previous_hash
		))
		return SHA256.new(block_info.encode()).hexdigest()

	'''
	Add a transaction to the block:
	Essentially append it to transactions list
	'''
	def add_transaction(self, transaction):
		self.transactions.append(transaction)
