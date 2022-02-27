class Blockchain:

    '''
    Initialized a Blockchain object

    Attributes
    ----------
    blocks: list of Block
        the blocks that this blockchain contains
    '''
    def __init__(self):
        self.blocks = []

    '''
    Appends a new block to the list of Block
    '''
    def add_block(self, block):
        self.blocks.append(block)