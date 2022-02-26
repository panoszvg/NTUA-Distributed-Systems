import base64
from collections import OrderedDict

import binascii
from inspect import signature

import Crypto
import Crypto.Random
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

import json
import requests
from flask import Flask, jsonify, request, render_template
from rsa import sign


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
        self.transaction_inputs = transaction_inputs # λίστα από Transaction Input 
        self.transaction_outputs = [] # λίστα από Transaction Output
        self.transaction_id = self.get_hash().hexdigest() # το hash του transaction
        self.signature = None

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
        return SHA256.new(transaction_info.encode())
    
    def to_dict(self):
        return dict(
            sender_address = self.sender_address,
            receiver_address = self.receiver_address,
            amount = self.amount,
            transaction_id = self.transaction_id,
            transaction_inputs = self.transaction_inputs,
            transaction_outputs = self.transaction_outputs,
            signature = self.signature
        )
        

    """
    Sign transaction with private key

    Parameters
    ----------
    private_key: str
        the private key of the sender's wallet
    """
    def sign_transaction(self, private_key):
        hash_obj = self.get_hash()
        rsa = RSA.import_key(private_key)
        signer = PKCS1_v1_5.new(rsa)
        signature = signer.sign(hash_obj)
        self.signature = base64.b64encode(signature)
       