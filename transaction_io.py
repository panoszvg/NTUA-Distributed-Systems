class Transaction_Input:
    '''
    Create a Transaction_Input object

    Attributes
    ----------
    previous_output_id: str
        id of the transaction output where the amount came from
    '''
    def __init__(self, previous_output_id):
        self.previous_output_id = previous_output_id

    def to_dict(self):
        return dict(previous_output_id = self.previous_output_id)

    
class Transaction_Output:
    '''
    Create a Transaction_Output object

    Attributes
    ----------
    id: str
        id that comes from the transaction it is part of
    recipient: int
        id of the transaction's recipient (new coin owner)
    amount: int
        the amount transferred
    '''
    def __init__(self, transaction_id, recipient, amount):
        self.id = transaction_id
        self.recipient = recipient
        self.amount = amount

    def to_dict(self):
        return dict(
            id = self.id,
            recipient = self.recipient,
            amount = self.amount
        )