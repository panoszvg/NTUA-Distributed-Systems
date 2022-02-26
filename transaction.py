from collections import OrderedDict

import binascii

import Crypto
import Crypto.Random
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

import json
import requests
from flask import Flask, jsonify, request, render_template


class Transaction:

    '''
    Initialize a Transaction object with necessary information:

    Attributes
    ----------
    sender_address: str
        public key of the sender's wallet
    receiver_address: str
        public key of receiver's wallet
    amount: int
        amount of NBC to be transferred
    transaction_id: str
        hash string of the transaction - using parameters above
    transaction_inputs: list(str)
        list that contains transactions ids as inputs
    transaction_outputs: list(str)
        list that contains UTXOs
    '''
    def __init__(self, sender_address, receiver_address, amount, transaction_inputs):
        self.sender_address = sender_address # To public key του wallet από το οποίο προέρχονται τα χρήματα
        self.receiver_address = receiver_address # To public key του wallet στο οποίο θα καταλήξουν τα χρήματα
        self.amount = amount # το ποσό που θα μεταφερθεί
        self.transaction_id = self.get_hash() # το hash του transaction
        self.transaction_inputs = transaction_inputs # λίστα από Transaction Input 
        self.transaction_outputs = [] # λίστα από Transaction Output 

    '''
    Function that returns hash string used as transaction_id,
    using transaction information 
    
    return: str
    '''
    def get_hash(self):
        transaction_info = json.dumps(dict(
            sender_address = self.sender_address,
            receiver_address = self.receiver_address,
            amount = self.amount,
            transaction_inputs = self.transaction_inputs
        ))
        return SHA256.new(transaction_info.encode()).hexdigest()
    


    def to_dict(self):
        

    def sign_transaction(self):
        """
        Sign transaction with private key
        """
       