import binascii

import Crypto
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4



class Wallet:

	'''
	Initialize a Wallet object that belongs to a Node in the network
	'''
	def __init__(self):
		rand_gen = RSA.generate(2048)
		self.public_key = rand_gen.publickey().export_key().decode() 
		self.private_key = rand_gen.export_key().decode() 
		#self_address
		self.transactions = []

	# def balance():

