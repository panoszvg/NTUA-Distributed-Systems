class Blockchain:

    '''
    Initialized a Blockchain object

    Attributes
    ----------
    blocks: list of Block
        the blocks that this blockchain contains
    '''
    def __init__(self, capacity):
        self.blocks = []
        self.capacity = capacity

    '''
    Appends a new block to the list of Block
    '''
    def add_block(self, block):
        self.blocks.append(block)

    def get_transactions(self):
        transactions = []
        for block in self.blocks:
            for transaction in block.transactions:
                transactions.append(transaction)
        return transactions