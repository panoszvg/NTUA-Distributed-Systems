from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

class Wallet:

	'''
	Initialize a Wallet object that belongs to a Node in the network
	'''
	def __init__(self):
		private_key = rsa.generate_private_key(
			public_exponent=65537,
			key_size=4096,
			backend=default_backend()
		)
		self.private_key = private_key.private_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PrivateFormat.PKCS8,
			encryption_algorithm=serialization.NoEncryption()
		)

		public_key = private_key.public_key()
		
		self.public_key = public_key.public_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PublicFormat.SubjectPublicKeyInfo
		)

		self.transactions = []
